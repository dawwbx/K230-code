# ============================================================
# 数据集工具 - 中心化配置
# 类别本身存在 classes.json 里（HSV 用 5_hsv_picker.py 调色）
# ============================================================
import os
import json
import numpy as np

# ---- 路径 ----
DEFAULT_INPUT_DIR = r"C:\Users\pc\Desktop\p"   # 默认输入文件夹（手机拍的原图）
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "dataset")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
XML_DIR    = os.path.join(OUTPUT_DIR, "xml")
ZIP_NAME   = "dataset_for_aicube.zip"
CLASSES_JSON = os.path.join(os.path.dirname(__file__), "classes.json")
LAST_INPUT_FILE = os.path.join(os.path.dirname(__file__), ".last_input_dir")


def _save_last_input(path):
    try:
        with open(LAST_INPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(path)
    except OSError:
        pass


def peek_last_input_dir():
    """读取上次实际使用的输入文件夹（不提示用户）。
       返回路径字符串或 None。"""
    if os.path.exists(LAST_INPUT_FILE):
        try:
            with open(LAST_INPUT_FILE, 'r', encoding='utf-8') as f:
                p = f.read().strip()
                if p and os.path.isdir(p):
                    return p
        except OSError:
            pass
    if os.path.isdir(DEFAULT_INPUT_DIR):
        return DEFAULT_INPUT_DIR
    return None


def get_input_dir():
    """返回当前要使用的输入文件夹。
       - 默认路径存在 -> 直接返回（并记录）
       - 不存在 -> 终端提示用户输入（也会记录所选）
       - 用户输入 'q' 或留空 -> 返回 None
    """
    if os.path.isdir(DEFAULT_INPUT_DIR):
        _save_last_input(DEFAULT_INPUT_DIR)
        return DEFAULT_INPUT_DIR
    # 默认路径找不到时，先看看上次记的能不能复用
    last = peek_last_input_dir()
    if last:
        ans = input(f"Use last folder [{last}]? (Y/n): ").strip().lower()
        if ans in ('', 'y'):
            return last
    print(f"[INFO] default folder not found: {DEFAULT_INPUT_DIR}")
    while True:
        p = input("Enter input folder path (or 'q' to quit): ").strip().strip('"').strip("'")
        if not p or p.lower() == 'q':
            return None
        if os.path.isdir(p):
            _save_last_input(p)
            return p
        print(f"  [WARN] not a directory: {p}")


# ---- 图像处理 ----
MAX_SIZE = 1280   # 长边压到这个像素以内（AI Cube 单文件 10MB 限制）
BOX_PADDING = 6   # 自动标注框向外扩 N 像素

# ---- 可疑判定（labelfix 用）----
SUSPICIOUS_MIN = 0.005
SUSPICIOUS_MAX = 0.60

# ---- labelfix 窗口大小 ----
WIN_MAX = 1100


# ---- 类别加载 / 保存 ----
_DEFAULT_CLASSES = [
    {
        "name":        "plate",
        "hsv_lower":   [10,  30,  80],
        "hsv_upper":   [35, 200, 240],
        "min_ratio":   0.005,
        "max_ratio":   0.6,
        "kernel":      25,
        "multi_boxes": False,
    },
]


def _load_classes_raw():
    """从 JSON 文件读 classes；不存在则用默认值生成。"""
    if not os.path.exists(CLASSES_JSON):
        with open(CLASSES_JSON, 'w', encoding='utf-8') as f:
            json.dump(_DEFAULT_CLASSES, f, indent=2, ensure_ascii=False)
        return list(_DEFAULT_CLASSES)
    with open(CLASSES_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def _to_runtime(raw_list):
    """JSON 里 hsv 是 list，运行时转 numpy.array。"""
    out = []
    for c in raw_list:
        d = dict(c)
        d['hsv_lower'] = np.array(c['hsv_lower'], dtype=np.uint8)
        d['hsv_upper'] = np.array(c['hsv_upper'], dtype=np.uint8)
        out.append(d)
    return out


CLASSES = _to_runtime(_load_classes_raw())


def class_names():
    return [c["name"] for c in CLASSES]


def save_class(cls_dict, target_idx=None):
    """把单个类别写回 classes.json。
       target_idx=None: 同名覆盖，否则末尾追加
       target_idx=int : 替换第 idx 个
    """
    raw = _load_classes_raw()
    # numpy -> list 以便 JSON 序列化
    s = dict(cls_dict)
    if isinstance(s.get('hsv_lower'), np.ndarray):
        s['hsv_lower'] = s['hsv_lower'].tolist()
    if isinstance(s.get('hsv_upper'), np.ndarray):
        s['hsv_upper'] = s['hsv_upper'].tolist()
    # 确保类型干净
    s['hsv_lower'] = [int(v) for v in s['hsv_lower']]
    s['hsv_upper'] = [int(v) for v in s['hsv_upper']]
    s['min_ratio'] = float(s.get('min_ratio', 0.005))
    s['max_ratio'] = float(s.get('max_ratio', 0.6))
    s['kernel']    = int(s.get('kernel', 25))
    s['multi_boxes'] = bool(s.get('multi_boxes', False))

    if target_idx is not None:
        raw[target_idx] = s
    else:
        for i, c in enumerate(raw):
            if c['name'] == s['name']:
                raw[i] = s
                break
        else:
            raw.append(s)

    with open(CLASSES_JSON, 'w', encoding='utf-8') as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)

    global CLASSES
    CLASSES = _to_runtime(raw)


def delete_class(target_idx):
    """删除第 idx 个类别。"""
    raw = _load_classes_raw()
    if 0 <= target_idx < len(raw):
        del raw[target_idx]
        with open(CLASSES_JSON, 'w', encoding='utf-8') as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
        global CLASSES
        CLASSES = _to_runtime(raw)
        return True
    return False
