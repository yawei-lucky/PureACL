import cv2
import numpy as np
import glob
import os
import matplotlib.pyplot as plt

# 棋盘格尺寸（9x6）
checkerboard_size = (9, 6)
# 每个棋盘格方块的实际尺寸（单位：米，调整为你的棋盘格尺寸）
square_size = 0.025

# 准备棋盘格的3D点，例如 (0,0,0), (1,0,0), (2,0,0), ... (8,5,0)
objp = np.zeros((checkerboard_size[0] * checkerboard_size[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:checkerboard_size[0], 0:checkerboard_size[1]].T.reshape(-1, 2)
objp *= square_size  # 调整为实际尺寸

# 用于存储3D点和2D点
objpoints = []  # 3D点（世界坐标系）
imgpoints = []  # 2D点（图像坐标系）

# 读取标定图片
image_folder = '/data/yawei/PureACL/drone/camera_cali/images/'  # 替换为你的标定图片路径
images = glob.glob(os.path.join(image_folder, '*.jpg'))

for fname in images:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 寻找棋盘格角点
    ret, corners = cv2.findChessboardCorners(gray, checkerboard_size, None)

    if ret:
        objpoints.append(objp)
        imgpoints.append(corners)

        # 可视化检测到的角点并保存到输入文件夹
        img_with_corners = cv2.drawChessboardCorners(img, checkerboard_size, corners, ret)
        output_path = os.path.join(image_folder, f'detected_corners_{os.path.basename(fname)}')
        plt.imshow(cv2.cvtColor(img_with_corners, cv2.COLOR_BGR2RGB))
        plt.title(f'Detected Corners - {os.path.basename(fname)}')
        plt.axis('off')
        plt.savefig(output_path)
        plt.close()

# 相机标定
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

# 输出标定结果
print("相机内参矩阵（K）：\n", mtx)
print("畸变系数（dist）：\n", dist)

# 矫正标定图片并保存到输入文件夹
for fname in images:
    img = cv2.imread(fname)
    h, w = img.shape[:2]
    newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))

    # 畸变校正
    dst = cv2.undistort(img, mtx, dist, None, newcameramtx)

    # 裁剪图像
    x, y, w, h = roi
    dst = dst[y:y+h, x:x+w]

    # 保存矫正后的图像
    calibrated_filename = os.path.join(image_folder, f'calibrated_{os.path.basename(fname)}')
    cv2.imwrite(calibrated_filename, dst)

    # 可视化原始和矫正结果并保存到输入文件夹
    comparison_filename = os.path.join(image_folder, f'comparison_{os.path.basename(fname)}')
    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    plt.title('Original Image')
    plt.axis('off')

    plt.subplot(1, 2, 2)
    plt.imshow(cv2.cvtColor(dst, cv2.COLOR_BGR2RGB))
    plt.title('Calibrated Image')
    plt.axis('off')

    plt.savefig(comparison_filename)
    plt.close()

print(f"所有结果已保存到原始文件夹：{image_folder}")
