import torch
from numpy.core import multiarray
# 添加 `multiarray` 到全局允许列表
torch.serialization.add_safe_globals([multiarray])
ckpt = torch.load("/data/yawei/PureACL/outputs/training/ford/checkpoint_390.tar", map_location='cpu')
torch.save(ckpt, "new_checkpoint.pth")
