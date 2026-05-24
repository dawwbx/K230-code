# 交互式 HSV 取色器
# 给一张代表性照片，拖框框住目标 → 自动算 HSV 范围 → 实时看 mask 是否准
# 满意了按 S 保存到 classes.json，新建/更新类别都靠它
#
# 操作键：
#   左键拖拽 = 框出目标区域（拖一次更新一次 HSV）
#   M       = 切换 mask 高亮显示
#   +/-     = 放宽/收紧 HSV 容差
#   N       = 换下一张样品图（继续看 mask 准不准）
#   S       = 保存当前 HSV 到类别
#   Q / ESC = 退出不保存

import cv2
import numpy as np
import os
import sys
from pathlib import Path

import config as C


class S:
    img_path = None
    img_orig = None     # 原图 BGR（未缩放，用来算 HSV）
    img_hsv  = None     # 原图 HSV
    img_disp = None     # 缩放后的显示图
    scale = 1.0

    drawing = False
    start = None
    end   = None
    roi   = None        # 原图坐标 (x1,y1,x2,y2)

    h_lo = s_lo = v_lo = 0
    h_hi = s_hi = v_hi = 255
    margin = 10
    show_mask = True


def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def pick_sample_files():
    """返回一组可用的样品图（input dir 优先，fallback 到 dataset/images）"""
    input_dir = C.get_input_dir()
    files = []
    if input_dir:
        for ext in ('*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG'):
            files.extend(Path(input_dir).glob(ext))
    if not files and os.path.isdir(C.IMAGES_DIR):
        files = list(Path(C.IMAGES_DIR).glob('*.jpg'))
    return sorted(set(files))


def load_image(p):
    img = imread_unicode(p)
    if img is None:
        return False
    h, w = img.shape[:2]
    sc = min(C.WIN_MAX / max(h, w), 1.0)
    S.img_orig = img
    S.img_hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    S.img_disp = cv2.resize(img, (int(w*sc), int(h*sc))) if sc < 1 else img.copy()
    S.scale = sc
    S.img_path = p
    # 不清 ROI/HSV，让用户能在新图上继续验证旧 mask
    return True


def compute_hsv():
    if S.roi is None:
        return
    x1, y1, x2, y2 = S.roi
    patch = S.img_hsv[y1:y2, x1:x2]
    if patch.size == 0:
        return
    h_vals = patch[..., 0].flatten()
    s_vals = patch[..., 1].flatten()
    v_vals = patch[..., 2].flatten()
    # 5~95 percentile 去掉边缘噪声，再加上 margin 余量
    S.h_lo = max(0,   int(np.percentile(h_vals,  5)) - S.margin)
    S.h_hi = min(180, int(np.percentile(h_vals, 95)) + S.margin)
    S.s_lo = max(0,   int(np.percentile(s_vals,  5)) - S.margin)
    S.s_hi = min(255, int(np.percentile(s_vals, 95)) + S.margin)
    S.v_lo = max(0,   int(np.percentile(v_vals,  5)) - S.margin)
    S.v_hi = min(255, int(np.percentile(v_vals, 95)) + S.margin)


def on_mouse(event, x, y, flags, _):
    if event == cv2.EVENT_LBUTTONDOWN:
        S.drawing = True
        S.start = (x, y)
        S.end = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE and S.drawing:
        S.end = (x, y)
    elif event == cv2.EVENT_LBUTTONUP and S.drawing:
        S.drawing = False
        S.end = (x, y)
        x1 = int(min(S.start[0], S.end[0]) / S.scale)
        y1 = int(min(S.start[1], S.end[1]) / S.scale)
        x2 = int(max(S.start[0], S.end[0]) / S.scale)
        y2 = int(max(S.start[1], S.end[1]) / S.scale)
        if x2 - x1 > 5 and y2 - y1 > 5:
            S.roi = (x1, y1, x2, y2)
            compute_hsv()


def render(class_name, file_idx, file_total):
    img = S.img_disp.copy()

    # mask 高亮（在当前显示图上把符合范围的像素染绿）
    if S.show_mask:
        lower = np.array([S.h_lo, S.s_lo, S.v_lo], dtype=np.uint8)
        upper = np.array([S.h_hi, S.s_hi, S.v_hi], dtype=np.uint8)
        hsv_disp = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_disp, lower, upper)
        overlay = img.copy()
        overlay[mask > 0] = (0, 255, 0)
        img = cv2.addWeighted(img, 0.55, overlay, 0.45, 0)

    # 显示当前 ROI
    if S.roi:
        x1, y1, x2, y2 = S.roi
        cv2.rectangle(img,
                      (int(x1*S.scale), int(y1*S.scale)),
                      (int(x2*S.scale), int(y2*S.scale)),
                      (0, 200, 255), 2)
    # 正在拖的
    if S.drawing and S.start and S.end:
        cv2.rectangle(img, S.start, S.end, (0, 255, 255), 2)

    H, W = img.shape[:2]
    # 顶部信息条
    top = f"Class:[{class_name}]  Sample {file_idx+1}/{file_total}  {S.img_path.name}"
    cv2.rectangle(img, (0, 0), (W, 28), (0, 0, 0), -1)
    cv2.putText(img, top, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    # HSV 当前值
    hsv_line = f"HSV lower=[{S.h_lo:3d},{S.s_lo:3d},{S.v_lo:3d}]  upper=[{S.h_hi:3d},{S.s_hi:3d},{S.v_hi:3d}]  margin={S.margin}  mask={'ON' if S.show_mask else 'OFF'}"
    cv2.rectangle(img, (0, H-48), (W, H-24), (40, 40, 40), -1)
    cv2.putText(img, hsv_line, (8, H-30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # 底部帮助
    help_txt = "LMB=drag-target  M=mask  +/-=widen/narrow  N=next-image  S=save  Q=quit"
    cv2.rectangle(img, (0, H-24), (W, H), (0, 0, 0), -1)
    cv2.putText(img, help_txt, (8, H-6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    return img


def ask_target_class():
    """终端里问要调哪个类别。返回 (target_idx_or_None, name)。"""
    print("\nExisting classes:")
    for i, c in enumerate(C.CLASSES):
        lo = c['hsv_lower'].tolist()
        hi = c['hsv_upper'].tolist()
        print(f"  [{i+1}] {c['name']:12s}  HSV {lo} ~ {hi}")
    print("  [n] new class")
    print("  [q] quit")
    sel = input("Tune which? ").strip().lower()

    if sel in ('q', ''):
        return 'quit', None
    if sel == 'n':
        name = input("New class name (English, no spaces): ").strip()
        if not name:
            return 'quit', None
        return None, name
    try:
        idx = int(sel) - 1
        if not (0 <= idx < len(C.CLASSES)):
            print("Invalid choice.")
            return 'quit', None
        return idx, C.CLASSES[idx]['name']
    except ValueError:
        print("Invalid input.")
        return 'quit', None


def main():
    target_idx, name = ask_target_class()
    if target_idx == 'quit':
        return

    files = pick_sample_files()
    if not files:
        print("[ERROR] no images to sample from")
        return

    fi = 0
    if not load_image(files[fi]):
        print(f"Cannot read {files[fi]}")
        return

    # 现有类别：把已有 HSV 灌进去作为起点
    if target_idx is not None and target_idx < len(C.CLASSES):
        c = C.CLASSES[target_idx]
        S.h_lo, S.s_lo, S.v_lo = [int(v) for v in c['hsv_lower']]
        S.h_hi, S.s_hi, S.v_hi = [int(v) for v in c['hsv_upper']]

    cv2.namedWindow("hsv_picker", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("hsv_picker", on_mouse)

    while True:
        cv2.imshow("hsv_picker", render(name, fi, len(files)))
        key = cv2.waitKey(20) & 0xFF
        if key == 255:
            continue
        if key in (ord('q'), 27):
            print("Quit without saving.")
            break
        elif key == ord('m'):
            S.show_mask = not S.show_mask
        elif key in (ord('+'), ord('=')):
            S.margin = min(S.margin + 5, 80)
            compute_hsv()
        elif key in (ord('-'), ord('_')):
            S.margin = max(0, S.margin - 5)
            compute_hsv()
        elif key == ord('n'):
            fi = (fi + 1) % len(files)
            load_image(files[fi])
        elif key == ord('s'):
            if S.roi is None and target_idx is None:
                print("[!] Drag a rectangle on the target first.")
                continue
            mb_in = input("Multiple instances per image? (y/N): ").strip().lower()
            multi = (mb_in == 'y')

            # 沿用已有或填默认值
            if target_idx is not None and target_idx < len(C.CLASSES):
                base = C.CLASSES[target_idx]
            else:
                base = {'min_ratio': 0.005, 'max_ratio': 0.6, 'kernel': 25}

            cls = {
                'name':        name,
                'hsv_lower':   [S.h_lo, S.s_lo, S.v_lo],
                'hsv_upper':   [S.h_hi, S.s_hi, S.v_hi],
                'min_ratio':   float(base.get('min_ratio', 0.005)),
                'max_ratio':   float(base.get('max_ratio', 0.6)),
                'kernel':      int(base.get('kernel', 25)),
                'multi_boxes': multi,
            }
            C.save_class(cls, target_idx=target_idx)
            print(f"\nSaved class '{name}'.")
            print(f"  HSV {cls['hsv_lower']} ~ {cls['hsv_upper']}")
            print(f"  multi_boxes = {multi}")
            break

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
