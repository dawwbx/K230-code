# ============================================================
# 数据集工具 - 中心化配置
# 加新类别就在这里改，其他脚本会自动跟上
# ============================================================
import os
import numpy as np

# ---- 路径 ----
DEFAULT_INPUT_DIR = r"C:\Users\pc\Desktop\p"   # 默认输入文件夹（手机拍的原图）
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "dataset")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
XML_DIR    = os.path.join(OUTPUT_DIR, "xml")
ZIP_NAME   = "dataset_for_aicube.zip"          # 输出 ZIP 名


def get_input_dir():
    """返回当前要使用的输入文件夹。
       - 默认路径存在 -> 直接返回
       - 默认路径不存在 -> 在终端提示用户输入路径
       - 用户输入 'q' 或留空 -> 返回 None（调用方应中止）
    """
    if os.path.isdir(DEFAULT_INPUT_DIR):
        return DEFAULT_INPUT_DIR
    print(f"[INFO] default folder not found: {DEFAULT_INPUT_DIR}")
    while True:
        p = input("Enter input folder path (or 'q' to quit): ").strip().strip('"').strip("'")
        if not p or p.lower() == 'q':
            return None
        if os.path.isdir(p):
            return p
        print(f"  [WARN] not a directory: {p}")

# ---- 图像处理 ----
MAX_SIZE = 1280   # 长边压到这个像素以内（AI Cube 单文件 10MB 限制）

# ---- 类别定义 ----
# 想识别几样东西，就在这个列表里加几个 dict
# name        : Pascal VOC XML 里的类别名
# hsv_lower   : HSV 下限（OpenCV 格式，H 是 0~180）
# hsv_upper   : HSV 上限
# min_ratio   : 最小面积比（< 这个值会被忽略，防止小噪点）
# max_ratio   : 最大面积比（> 这个值会被忽略，防止把背景框进来）
# kernel      : 形态学闭运算核大小（越大越能把碎块粘起来）
# multi_boxes : True = 同一类可有多个目标；False = 只取最大的那个
CLASSES = [
    {
        "name":        "plate",
        "hsv_lower":   np.array([10,  30,  80]),
        "hsv_upper":   np.array([35, 200, 240]),
        "min_ratio":   0.005,
        "max_ratio":   0.6,
        "kernel":      25,
        "multi_boxes": False,
    },
    # 想加第二类就把下面解开注释，改成你的物体颜色
    # {
    #     "name":        "ball",
    #     "hsv_lower":   np.array([20, 100, 100]),
    #     "hsv_upper":   np.array([35, 255, 255]),
    #     "min_ratio":   0.002,
    #     "max_ratio":   0.3,
    #     "kernel":      15,
    #     "multi_boxes": True,
    # },
]

# ---- 自动标注后的余量（向四周扩 N 像素，避免框太紧）----
BOX_PADDING = 6

# ---- 可疑判定（labelfix 用）----
# 单个框面积比例不在这个范围内的图会被标记为可疑
SUSPICIOUS_MIN = 0.005
SUSPICIOUS_MAX = 0.60

# ---- labelfix 窗口大小 ----
WIN_MAX = 1100


def class_names():
    return [c["name"] for c in CLASSES]
