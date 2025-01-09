import numpy as np

# 假设文件名为 "large_data.npy"
file_path = '/data/yawei/PureACL/ford_data_process/2017-10-26-V2-Log3/info_files/groundview_satellite_pair.npy'
# file_path = '/data/yawei/PureACL/drone/imu/2024-12-05_05-12-53/Orientation.csv'
data = np.load(file_path, mmap_mode='r')  # 以内存映射模式加载
# # 读取前 10 行，所有列
# subset_rows = data[:10, :]
# print("前 10 行数据：")
# print(subset_rows)

# 读取前 1 行，10列
subset_rows = data
print(subset_rows)

# # 读取第 5 行
# row_5 = data[4, :]
# print("第 5 行数据：")
# print(row_5)

# # 读取前 10 行，第 2 列到第 5 列
# subset_columns = data[:10, 1:5]
# print("前 10 行，第 2 列到第 5 列：")
# print(subset_columns)
