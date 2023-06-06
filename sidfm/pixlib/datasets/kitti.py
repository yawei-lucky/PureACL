# -*- coding: utf-8 -*-
"""
Created on Fri Dec  4 11:44:19 2020

@author: loocy
"""

from sidfm.pixlib.datasets.base_dataset import BaseDataset
import numpy as np
import os
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
import torch
import sidfm.pixlib.datasets.Kitti_utils as Kitti_utils
from matplotlib import pyplot as plt
# from sklearn.neighbors import NearestNeighbors
import kitti_data_process.Kitti_gps_coord_func as gps_func
import random
from sidfm.pixlib.datasets.transformations import euler_matrix
from sidfm.pixlib.geometry import Camera, Pose

pre_init = False
satmap_zoom = 18 
satmap_dir = 'satmap_'+str(satmap_zoom)
grdimage_dir = 'raw_data'
left_color_camera_dir = 'image_02/data'
right_color_camera_dir = 'image_03/data'
oxts_dir = 'oxts/data'
vel_dir = 'velodyne_points/data'

grd_ori_size = (375, 1242) # different size in Kitti 375×1242, 370×1224,374×1238, and376×1241, but 375×1242 in calibration
grd_process_size = (384, 1248)
satellite_ori_size = 1280
# query_grd_dis = 0.9054 #1.65-0.7446


ToTensor = transforms.Compose([
    transforms.ToTensor()])

def homography_trans(image, I_tar, I_src, E, N, height):
    # inputs:
    #   image: src image
    #   I_tar,I_src:camera
    #   E: pose
    #   N: ground normal
    #   height: ground height
    # return:
    #   out: tar image

    w, h = I_tar.size

    # get back warp matrix
    i = torch.arange(0, h)
    j = torch.arange(0, w)
    ii, jj = torch.meshgrid(i, j)  # i:h,j:w
    uv = torch.stack([jj, ii], dim=-1).float()  # shape = [h, w, 2]
    # ones = torch.ones_like(ii)
    # uv1 = torch.stack([jj, ii, ones], dim=-1).float()  # shape = [h, w, 3]

    p3D = I_tar.image2world(uv) # 2D->3D scale unknow

    depth = height / torch.einsum('...hwi,...i->...hw', p3D, N)
    depth = depth.clamp(0., 1000.)
    p3D_grd = depth[:,:,None] * p3D
    # each camera coordinate to 'query' coordinate
    p3d_ref = E * p3D_grd  # to sat
    uv,_ = I_src.world2image(p3d_ref)


    # lefttop to center
    uv_center = uv - I_src.size//2 #I_src.c  # shape = [h,w,2]
    # u:south, v: up from center to -1,-1 top left, 1,1 buttom right
    scale = I_src.size//2 #torch.max(I_src.size - I_src.c, I_src.c)
    uv_center /= scale

    out = torch.nn.functional.grid_sample(image.unsqueeze(0), uv_center.unsqueeze(0), mode='bilinear',
                        padding_mode='zeros')

    out = transforms.functional.to_pil_image(out.squeeze(0), mode='RGB')
    return out

class Kitti(BaseDataset):
    default_conf = {
        'dataset_dir': '/data/dataset/Kitti', #"/home/shan/data/Kitti", #
        'mul_query': False,
    }

    def _init(self, conf):
        pass

    def get_dataset(self, split):
        #assert split != 'test', 'Not supported'
        return _Dataset(self.conf, split)

def read_calib(calib_file_name, camera_id='rect_02'):
    with open(calib_file_name, 'r') as f:
        lines = f.readlines()
        for line in lines:
            # left color camera k matrix
            if 'P_'+camera_id in line:
                # get 3*3 matrix from P_rect_**:
                items = line.split(':')
                valus = items[1].strip().split(' ')

                camera_P = np.asarray([float(i) for i in valus]).reshape((3, 4))
                # split P into K and T
                fx = float(valus[0])
                cx = float(valus[2])
                fy = float(valus[5])
                cy = float(valus[6])

                camera_k = [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
                camera_k = np.asarray(camera_k)
                tx, ty, tz = float(valus[3]), float(valus[7]), float(valus[11])
                camera_t = np.linalg.inv(camera_k) @ np.asarray([tx, ty, tz])
                camera_ex = np.hstack((np.eye(3), camera_t.reshape(3,1)))
                camera_ex = np.vstack((camera_ex, np.array([0,0,0,1])))
            #  add R_rect_00: P_rect_xx * R_rect_00 * (R|T)_velo_to_cam * X
            if 'R_rect_00' in line:
                items = line.split(':')
                valus = items[1].strip().split(' ')
                camera_R0 = np.asarray([float(i) for i in valus]).reshape((3, 3))
                camera_R0 = np.hstack((camera_R0, np.zeros([3, 1])))
                camera_R0 = np.vstack((camera_R0, np.array([0,0,0,1])))
        camera_ex = camera_ex @ camera_R0

    return camera_k, camera_ex


def read_sensor_rel_pose(file_name):
    with open(file_name, 'r') as f:
        lines = f.readlines()
        for line in lines:
            # left color camera k matrix
            if 'R' in line:
                # get 3*3 matrix from P_rect_**:
                items = line.split(':')
                valus = items[1].strip().split(' ')
                R = np.asarray([float(i) for i in valus]).reshape((3, 3))

            if 'T' in line:
                # get 3*3 matrix from P_rect_**:
                items = line.split(':')
                valus = items[1].strip().split(' ')
                T = np.asarray([float(i) for i in valus]).reshape((3))
    rel_pose_hom = np.eye(4)
    rel_pose_hom[:3, :3] = R
    rel_pose_hom[:3, 3] = T

    return R, T, rel_pose_hom

class _Dataset(Dataset):
    def __init__(self, conf, split):
        self.root = conf.dataset_dir
        self.conf = conf

        self.sat_pair = np.load(os.path.join(self.root, grdimage_dir, 'groundview_satellite_pair_'+str(satmap_zoom)+'.npy'), allow_pickle=True)

        # read form txt files
        self.file_name = []
        txt_file_name = os.path.join(self.root, grdimage_dir, 'kitti_split', split+'_files.txt')
        with open(txt_file_name, "r") as txt_f:
            lines = txt_f.readlines()
            for line in lines:
                line = line.strip()
                # check grb file exist
                grb_file_name = os.path.join(self.root, grdimage_dir, line[:38], left_color_camera_dir,
                                                  line[38:].lower())
                if not os.path.exists(grb_file_name):
                    print(grb_file_name + ' do not exist!!!')
                    continue

                self.file_name.append(line)

        if 0: # for 1 item
            self.file_name = random.sample(self.file_name, 1)
        if 0:  # for debug
            if split == 'train':
                self.file_name = random.sample(self.file_name, len(self.file_name)//10)
            else:
                self.file_name = random.sample(self.file_name, len(self.file_name)//20)

    def __len__(self):
        return len(self.file_name)

    def __getitem__(self, idx):
        # read cemera k matrix from camera calibration files
        file_name = self.file_name[idx]
        day_dir = file_name[:10]
        drive_dir = file_name[:38]
        image_no = file_name[38:]

        # get calibration information, do not adjust image size change here
        camera_k, camera_ex = read_calib(
            os.path.join(self.root, grdimage_dir, day_dir, 'calib_cam_to_cam.txt'))
        if self.conf['mul_query']:
            camera_r_k, camera_r_ex = read_calib(
                os.path.join(self.root, grdimage_dir, day_dir, 'calib_cam_to_cam.txt'), 'rect_03')
        imu2lidar_R, imu2lidar_T, imu2lidar_H = read_sensor_rel_pose(
            os.path.join(self.root, grdimage_dir, day_dir, 'calib_imu_to_velo.txt'))
        pose_imu2lidar = Pose.from_4x4mat(imu2lidar_H)
        lidar2cam_R, lidar2cam_T, lidar2cam_H = read_sensor_rel_pose(
            os.path.join(self.root, grdimage_dir, day_dir, 'calib_velo_to_cam.txt'))
        pose_lidar2cam = Pose.from_4x4mat(lidar2cam_H)
        # computer the relative pose between imu to camera
        imu2camera = pose_lidar2cam.compose(pose_imu2lidar)

        # get location & rotation
        oxts_file_name = os.path.join(self.root, grdimage_dir, drive_dir, oxts_dir,
                                      image_no.lower().replace('.png', '.txt'))
        with open(oxts_file_name, 'r') as f:
            content = f.readline().split(' ')
        location = [float(content[0]), float(content[1]), float(content[2])]
        roll, pitch, heading = float(content[3]), float(content[4]), float(content[5])

        # ground images, left color camera
        left_img_name = os.path.join(self.root, grdimage_dir, drive_dir, left_color_camera_dir, image_no.lower())
        with Image.open(left_img_name, 'r') as GrdImg:
            grd_left = GrdImg.convert('RGB')
            # resize
            grd_left = transforms.functional.resize(grd_left, grd_process_size)
            # process camera_k for resize
            camera_k[0] *= grd_process_size[1]/grd_ori_size[1]
            camera_k[1] *= grd_process_size[0]/grd_ori_size[0]
            grd_left = ToTensor(grd_left)

        # ground images, right color camera
        if self.conf['mul_query']:
            right_img_name = os.path.join(self.root, grdimage_dir, drive_dir, right_color_camera_dir, image_no.lower())
            with Image.open(right_img_name, 'r') as GrdImg:
                grd_right = GrdImg.convert('RGB')
                # resize
                grd_right = transforms.functional.resize(grd_right, grd_process_size)
                grd_right = ToTensor(grd_right)
                # process camera_r_k for resize
                camera_r_k[0] *= grd_process_size[1] / grd_ori_size[1]
                camera_r_k[1] *= grd_process_size[0] / grd_ori_size[0]

        # grd left
        camera_para = (camera_k[0,0],camera_k[1,1],camera_k[0,2],camera_k[1,2])
        camera = Camera.from_colmap(dict(
            model='PINHOLE', params=camera_para,
            width=int(grd_process_size[1]), height=int(grd_process_size[0])))
        imu2camera_left = Pose.from_4x4mat(camera_ex) @ imu2camera
        # same coordinate with ford body for better generability: IMU pose, x: forword, y:left, z:up -> x: forword, y:right, z:down
        body2imu = Pose.from_4x4mat(
            np.array([[1., 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]))  # no shift, x->x, y->-y, z->-z
        grd_image = {
            # to array, when have multi query
            'image': grd_left.float(),
            'camera': camera.float(),
            'T_w2cam': (imu2camera_left@body2imu).float(),  # query is IMU pose, x: forword, y:right, z:down
            'camera_h': torch.tensor(1.65)
        }

        # grd right
        if self.conf['mul_query']:
            camera_para = (camera_r_k[0, 0], camera_r_k[1, 1], camera_r_k[0, 2], camera_r_k[1, 2])
            camera = Camera.from_colmap(dict(
                model='PINHOLE', params=camera_para,
                width=int(grd_process_size[1]), height=int(grd_process_size[0])))
            imu2camera_right = Pose.from_4x4mat(camera_r_ex) @ imu2camera
            grd_image_r = {
                # to array, when have multi query
                'image': grd_right.float(),
                'camera': camera.float(),
                'T_w2cam': (imu2camera_right@body2imu).float(), # query is IMU pose, IMU2CameraRight
                'camera_h': torch.tensor(1.65)
            }

        # satellite map
        SatMap_name = self.sat_pair.item().get(file_name)
        sat_gps = SatMap_name.split('_')
        sat_gps = [float(sat_gps[3]), float(sat_gps[5])]
        SatMap_name = os.path.join(self.root, satmap_dir, SatMap_name)
        with Image.open(SatMap_name, 'r') as SatMap:
            sat_map = SatMap.convert('RGB')
            sat_map = ToTensor(sat_map)

        # get ground-view, satellite image shift
        x_sg, y_sg = gps_func.angular_distance_to_xy_distance_v2(sat_gps[0], sat_gps[1], location[0],
                                                                 location[1])
        meter_per_pixel = Kitti_utils.get_meter_per_pixel(satmap_zoom, scale=1)
        x_sg = int(x_sg / meter_per_pixel)
        y_sg = int(-y_sg / meter_per_pixel)
        # query to satellite R
        ENU2sat_R = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])  # up->-sat z; east->sat x, north->-sat y
        ENU2sat = Pose.from_Rt(ENU2sat_R, np.array([0.,0,0])) #np.array([x_sg,y_sg,0]) shift in K

        # sat
        camera = Camera.from_colmap(dict(
            model='SIMPLE_PINHOLE',
            params=(1 / meter_per_pixel, x_sg+satellite_ori_size / 2.0, y_sg+satellite_ori_size / 2.0, 0, 0, 0, 0, np.infty),
            # np.infty for parallel projection
            width=int(satellite_ori_size), height=int(satellite_ori_size)))
        sat_image = {
            'image': sat_map.float(),
            'camera': camera.float(),
            'T_w2cam': Pose.from_4x4mat(np.eye(4)).float()  # grd 2 sat in q2r, so just eye(4)
        }

        normal = torch.tensor([[0., 0, 1]])  # down, z axis of body coordinate
        # calculate road Normal for key point from camera 2D to 3D, in query coordinate
        # normal = torch.tensor([0.,0, 1]) # down, z axis of body coordinate
        # # ignore roll angle, point to sea level,  only left pitch
        # ignore_roll = Pose.from_4x4mat(euler_matrix(-roll, 0, 0)).float()
        # normal = ignore_roll * normal

        imu2ENU = Pose.from_4x4mat(euler_matrix(roll, pitch, heading))# grd_x:east, grd_y:north, grd_z:up
        q2r_gt = ENU2sat@imu2ENU@body2imu # body -> sat

        if not pre_init:
            # ramdom shift translation and rotation on yaw/heading
            YawShiftRange = 15 * np.pi / 180  # in 15 degree
            yaw = 2 * YawShiftRange * np.random.random() - YawShiftRange
            # R_yaw = torch.tensor([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
            TShiftRange = 5  # in 5 meter
            T = 2 * TShiftRange * np.random.rand((3)) - TShiftRange
            T[2] = 0  # no shift on height

            # shift = Pose.from_Rt(R_yaw,T)
            R_yaw = euler_matrix(0, 0, yaw)
            shift = Pose.from_Rt(R_yaw[:3,:3], T)
            q2r_init = shift @ q2r_gt
        else:
            # use previous pose as initial pose
            if int(image_no[:-4]) == 0:
                q2r_init = q2r_gt
            else:
                pre_image_no = int(image_no[:-4])-1
                pre_image_no = "{:010d}".format(pre_image_no)
                pre_oxts_file_name = os.path.join(self.root, grdimage_dir, drive_dir, oxts_dir,
                                              pre_image_no + '.txt')
                with open(pre_oxts_file_name, 'r') as f:
                    content = f.readline().split(' ')
                pre_location = [float(content[0]), float(content[1]), float(content[2])]
                pre_roll, pre_pitch, pre_heading = float(content[3]), float(content[4]), float(content[5])
                # shift of previous gps
                dx, dy = gps_func.angular_distance_to_xy_distance_v2(location[0],
                                                                     location[1], pre_location[0], pre_location[1])
                if dx > 15 or dy > 15:
                    # not coutinue frames
                    q2r_init = q2r_gt
                else:
                    pre_imu2ENU = Pose.from_4x4mat(euler_matrix(pre_roll, pre_pitch, pre_heading))  # grd_x:east, grd_y:north, grd_z:up
                    # add ne shift
                    # get the pixel offsets of car pose
                    de_pixel = dx / meter_per_pixel # along the east direction
                    dn_pixel = dy / meter_per_pixel # along the north direction
                    enu_shift = Pose.from_Rt(np.eye(3),np.array([de_pixel,dn_pixel,0]))
                    q2r_init = ENU2sat @ enu_shift @ pre_imu2ENU @ body2imu  # body -> sat

        # scene
        data = {
            'ref': sat_image,
            'query': grd_image,
            'T_q2r_init': q2r_init.float(),
            'T_q2r_gt': q2r_gt.float(),
            'normal': normal.float(),
            #'grd_ratio': torch.tensor(0.6)
        }
        if self.conf['mul_query']:
            data['query_1'] = grd_image_r

        # debug
        if 0:
            fig = plt.figure(figsize=plt.figaspect(0.5))
            ax1 = fig.add_subplot(1, 2, 1)
            ax2 = fig.add_subplot(1, 2, 2)

            color_image0 = transforms.functional.to_pil_image(grd_left, mode='RGB')
            color_image0 = np.array(color_image0)
            if self.conf['mul_query']:
                # debug other grd_map
                color_image0 = transforms.functional.to_pil_image(grd_right, mode='RGB')
            # debug satellite map
            color_image1 = transforms.functional.to_pil_image(sat_map, mode='RGB')
            color_image1 = np.array(color_image1)

            ax1.imshow(color_image0)
            ax2.imshow(color_image1)
            #ax2.imshow(color_image1[380:900, 380:900])

            # camera position
            # camera gt position
            origin = torch.zeros(3)
            origin_2d_gt, _ = data['ref']['camera'].world2image(data['T_q2r_gt'] * origin)
            origin_2d_init, _ = data['ref']['camera'].world2image(data['T_q2r_init'] * origin)
            direct = torch.tensor([6.,0,0])
            direct = torch.tensor([0., 0, 0])
            direct = data['query']['T_w2cam'].inv()*direct
            direct_2d_gt, _ = data['ref']['camera'].world2image(data['T_q2r_gt'] * direct)
            direct_2d_init, _ = data['ref']['camera'].world2image(data['T_q2r_init'] * direct)
            origin_2d_gt = origin_2d_gt.squeeze(0)
            origin_2d_init = origin_2d_init.squeeze(0)
            direct_2d_gt = direct_2d_gt.squeeze(0)
            direct_2d_init = direct_2d_init.squeeze(0)

            # plot the init direction of the body frame
            plt.scatter(x=origin_2d_init[0], y=origin_2d_init[1], c='r', s=10)
            plt.quiver(origin_2d_init[0], origin_2d_init[1], direct_2d_init[0] - origin_2d_init[0],
                       origin_2d_init[1] - direct_2d_init[1], color=['r'], scale=None)
            # plot the gt direction of the body frame
            plt.scatter(x=origin_2d_gt[0], y=origin_2d_gt[1], c='g', s=10)
            plt.quiver(origin_2d_gt[0], origin_2d_gt[1], direct_2d_gt[0] - origin_2d_gt[0],
                       origin_2d_gt[1] - direct_2d_gt[1], color=['g'], scale=None)
            plt.show()
            print(idx,file_name, pitch, roll)

        # debug projection
        if 0:#idx % 50 == 0:
            if self.conf['mul_query'] > 0:
                query_list = ['query', 'query_1']
            else:
                query_list = ['query']
            # project ground to sat
            for q in query_list:
                E = data['T_q2r_gt']@data[q]['T_w2cam'].inv()
                N = torch.einsum('...ij,...cj->...ci', data[q]['T_w2cam'].R, data['normal'])
                tran_sat = homography_trans(data['ref']['image'], data[q]['camera'], data['ref']['camera'], E, N.squeeze(0), data[q]['camera_h'])
                fig = plt.figure(figsize=plt.figaspect(1.))
                ax1 = fig.add_subplot(2, 2, 1)
                ax2 = fig.add_subplot(2, 2, 2)
                ax3 = fig.add_subplot(2, 2, 3)
                ax4 = fig.add_subplot(2, 2, 4)
                ax1.imshow(tran_sat)
                q_img = transforms.functional.to_pil_image(data[q]['image'], mode='RGB')
                ax2.imshow(q_img)
                fusion = Image.blend(q_img.convert("RGBA"), tran_sat.convert("RGBA"), alpha=.6)
                ax4.imshow(fusion)
                sat_img = transforms.functional.to_pil_image(data['ref']['image'], mode='RGB')
                ax3.imshow(sat_img)
                # camera gt position
                origin = torch.zeros(3)
                origin_2d_gt, _ = data['ref']['camera'].world2image(data['T_q2r_gt'] * origin)
                direct = torch.tensor([0, 0, 20.])
                direct = data[q]['T_w2cam'].inv() * direct
                direct_2d_gt, _ = data['ref']['camera'].world2image(data['T_q2r_gt'] * direct)
                origin_2d_gt = origin_2d_gt.squeeze(0)
                direct_2d_gt = direct_2d_gt.squeeze(0)
                # plot the gt direction of the body frame
                ax3.scatter(x=origin_2d_gt[0], y=origin_2d_gt[1], c='r', s=5)
                ax3.quiver(origin_2d_gt[0], origin_2d_gt[1], direct_2d_gt[0] - origin_2d_gt[0],
                           origin_2d_gt[1] - direct_2d_gt[1], color=['r'], scale=None)

                plt.show()
                print(left_img_name, q)

        return data

if __name__ == '__main__':
    # test to load 1 data
    conf = {
        'dataset_dir': '/data/dataset/Kitti',  # "/home/shan/data/Kitti"'/home/shan/Dataset/Kitti', #
        'batch_size': 1,
        'num_workers': 0,
        'mul_query': False
    }
    dataset = Kitti(conf)
    loader = dataset.get_data_loader('test', shuffle=False)  # or 'train' ‘val’

    for i, data in zip(range(1000), loader):
        print(i)


