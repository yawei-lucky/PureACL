import os

# 定义 scene_images 目录路径
main_dir = "/data/yawei/PureACL/ford_data_process/drone/scene_images"

# 定义文件路径
train_txt_path = os.path.join(main_dir, "train.txt")
test_txt_path = os.path.join(main_dir, "test.txt")
pos_train_txt_path = os.path.join(main_dir, "groundview_pos_train.txt")
pos_test_txt_path = os.path.join(main_dir, "groundview_pos_test.txt")

# 定义文件夹与位置信息的对应关系
folder_positions = {
    "testa01": [0, 0, 0],
    "testa02": [2, 0, 0],
    "testa03": [2, 2, 0],
    "testa04": [5, 0, 0],
    "testa05": [5, 2, 0],
    "testa06": [8.5, 0, 0],
    "testa07": [8.5, 2, 0],
}

# 定义一个函数，通过图片名查找对应的位置
def get_position_from_image_name(image_name):
    for folder, position in folder_positions.items():
        if folder in image_name:  # 检查图片名是否包含文件夹名称
            return position
    return None  # 如果未找到，返回 None

# 根据 train.txt 生成 groundview_pos_train.txt
with open(train_txt_path, "r") as train_file, open(pos_train_txt_path, "w") as pos_train_file:
    for line in train_file:
        image_name = line.strip()
        position = get_position_from_image_name(image_name)
        if position:
            pos_train_file.write(f" {position[0]} {position[1]} {position[2]}\n")

# 根据 test.txt 生成 groundview_pos_test.txt
with open(test_txt_path, "r") as test_file, open(pos_test_txt_path, "w") as pos_test_file:
    for line in test_file:
        image_name = line.strip()
        position = get_position_from_image_name(image_name)
        if position:
            pos_test_file.write(f"{position[0]} {position[1]} {position[2]}\n")

print("Position files have been generated: groundview_pos_train.txt and groundview_pos_test.txt.")
