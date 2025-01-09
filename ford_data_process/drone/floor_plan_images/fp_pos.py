from logging import FATAL
import cv2
FATAL: 不能显示桌面 

# # 读取图像
image = cv2.imread("/data/yawei/PureACL/ford_data_process/drone/floor_plan_images/pure.jpg")

# # 获取图像的宽度和高度
# height, width, _ = image.shape
# print(f"图片大小：宽度={width}, 高度={height}")

# # 显示图像，并用鼠标点击设定坐标
# def click_event(event, x, y, flags, param):
#     if event == cv2.EVENT_LBUTTONDOWN:
#         print(f"你点击的位置：({x}, {y})")
#         # 在图像上标记点
#         cv2.circle(image, (x, y), 5, (0, 255, 0), -1)
#         cv2.imshow("Image", image)

# cv2.imshow("Image", image)
# cv2.setMouseCallback("Image", click_event)
# cv2.waitKey(0)
# cv2.destroyAllWindows()

# import cv2

# # 读取图片
# # image = cv2.imread("example.jpg")

# # 获取图片尺寸
# height, width, _ = image.shape

# # 计算中心点
# center_x = width // 2
# center_y = height // 2

# # 在图像上标记中心点（绿色圆点）
# cv2.circle(image, (center_x, center_y), 10, (0, 255, 0), -1)

# # 显示图片
# cv2.imshow("Image with Center", image)
# cv2.waitKey(0)
# cv2.destroyAllWindows()

