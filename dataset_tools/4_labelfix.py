# 极简边框标注/修正工具，纯 OpenCV，零 Qt 依赖
# 支持多类别、多框、点击删除
#
# 操作键：
#   左键拖拽   = 画新框（当前类别）
#   右键点击   = 删除点到的框
#   1 ~ 9     = 切换当前类别
#   D / →     = 下一张（自动保存）
#   A / ←     = 上一张（自动保存）
#   X         = 清空所有框
#   Z         = 撤销最后一个框
#   S         = 跳到下一个问题图
#   F         = 切换 "只看问题图 / 全部图"
#   Q / ESC   = 退出（自动保存）

import cv2
import numpy as np
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import config as C

CLASS_NAMES = C.class_names()
# 每类一个颜色 (BGR)
CLASS_COLORS = [
    (0, 255, 0),    # 绿
    (0, 165, 255),  # 橙
    (255, 100, 100),# 浅蓝
    (255, 0, 255),  # 紫
    (0, 255, 255),  # 黄
    (255, 255, 0),  # 青
    (180, 105, 255),# 粉
    (60, 60, 220),  # 红
    (200, 200, 200),# 灰
]


def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def parse_boxes(xml_path):
    """返回 [(class_idx, x1, y1, x2, y2), ...]，遇到未知类别忽略"""
    if not os.path.exists(xml_path):
        return []
    try:
        root = ET.parse(xml_path).getroot()
    except Exception:
        return []
    out = []
    for obj in root.findall('object'):
        name = obj.find('name').text
        if name not in CLASS_NAMES:
            continue
        ci = CLASS_NAMES.index(name)
        b = obj.find('bndbox')
        out.append((ci,
                    int(float(b.find('xmin').text)),
                    int(float(b.find('ymin').text)),
                    int(float(b.find('xmax').text)),
                    int(float(b.find('ymax').text))))
    return out


def save_xml(xml_path, img_name, w, h, boxes):
    root = Element('annotation')
    SubElement(root, 'folder').text = 'images'
    SubElement(root, 'filename').text = img_name
    size = SubElement(root, 'size')
    SubElement(size, 'width').text  = str(w)
    SubElement(size, 'height').text = str(h)
    SubElement(size, 'depth').text  = '3'
    SubElement(root, 'segmented').text = '0'
    for ci, x1, y1, x2, y2 in boxes:
        obj = SubElement(root, 'object')
        SubElement(obj, 'name').text = CLASS_NAMES[ci]
        SubElement(obj, 'pose').text = 'Unspecified'
        SubElement(obj, 'truncated').text = '0'
        SubElement(obj, 'difficult').text = '0'
        bnd = SubElement(obj, 'bndbox')
        SubElement(bnd, 'xmin').text = str(int(x1))
        SubElement(bnd, 'ymin').text = str(int(y1))
        SubElement(bnd, 'xmax').text = str(int(x2))
        SubElement(bnd, 'ymax').text = str(int(y2))
    pretty = minidom.parseString(tostring(root)).toprettyxml(indent="  ")
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(pretty)


def is_suspicious(img_w, img_h, boxes):
    """没框、面积过小、面积过大 都算可疑"""
    if not boxes:
        return True
    total = img_w * img_h
    for _, x1, y1, x2, y2 in boxes:
        r = ((x2-x1) * (y2-y1)) / total
        if r < C.SUSPICIOUS_MIN or r > C.SUSPICIOUS_MAX:
            return True
    return False


class State:
    def __init__(self):
        self.drawing = False
        self.start = None
        self.end = None
        self.boxes = []         # 原图坐标 [(ci,x1,y1,x2,y2),...]
        self.cur_class = 0      # 当前画框用的类别索引
        self.scale = 1.0
        self.img = None
        self.img_w = 0
        self.img_h = 0


state = State()


def on_mouse(event, x, y, flags, _):
    if event == cv2.EVENT_LBUTTONDOWN:
        state.drawing = True
        state.start = (x, y)
        state.end = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE and state.drawing:
        state.end = (x, y)
    elif event == cv2.EVENT_LBUTTONUP and state.drawing:
        state.drawing = False
        state.end = (x, y)
        x1 = min(state.start[0], state.end[0]) / state.scale
        y1 = min(state.start[1], state.end[1]) / state.scale
        x2 = max(state.start[0], state.end[0]) / state.scale
        y2 = max(state.start[1], state.end[1]) / state.scale
        if (x2 - x1) > 10 and (y2 - y1) > 10:
            state.boxes.append((state.cur_class,
                                int(max(0, x1)), int(max(0, y1)),
                                int(min(state.img_w, x2)), int(min(state.img_h, y2))))
        state.start = None
        state.end = None
    elif event == cv2.EVENT_RBUTTONDOWN:
        # 右键删除点中的框（取最小面积优先，避免大框挡住小框）
        ox = x / state.scale
        oy = y / state.scale
        hits = []
        for i, (ci, x1, y1, x2, y2) in enumerate(state.boxes):
            if x1 <= ox <= x2 and y1 <= oy <= y2:
                hits.append((i, (x2-x1)*(y2-y1)))
        if hits:
            hits.sort(key=lambda t: t[1])
            del state.boxes[hits[0][0]]


def render(filename, idx, total, only_susp, total_susp):
    img = state.img.copy()
    # 已确认的框
    for ci, x1, y1, x2, y2 in state.boxes:
        color = CLASS_COLORS[ci % len(CLASS_COLORS)]
        rx1, ry1 = int(x1*state.scale), int(y1*state.scale)
        rx2, ry2 = int(x2*state.scale), int(y2*state.scale)
        cv2.rectangle(img, (rx1, ry1), (rx2, ry2), color, 2)
        cv2.putText(img, CLASS_NAMES[ci], (rx1, max(20, ry1-6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    # 正在拖的框
    if state.drawing and state.start and state.end:
        c = CLASS_COLORS[state.cur_class % len(CLASS_COLORS)]
        cv2.rectangle(img, state.start, state.end, c, 2)

    H, W = img.shape[:2]
    # 顶部信息条
    mode = "SUSPICIOUS" if only_susp else "ALL"
    info = f"[{idx+1}/{total}] {filename}  | {mode}  | susp:{total_susp}  | boxes:{len(state.boxes)}"
    cv2.rectangle(img, (0, 0), (W, 30), (0, 0, 0), -1)
    cv2.putText(img, info, (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    # 类别条
    bar_y = 32
    cv2.rectangle(img, (0, bar_y), (W, bar_y+26), (40, 40, 40), -1)
    px = 8
    for i, n in enumerate(CLASS_NAMES):
        color = CLASS_COLORS[i % len(CLASS_COLORS)]
        active = (i == state.cur_class)
        label = f"[{i+1}]{n}"
        if active:
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(img, (px-3, bar_y+3), (px+tw+3, bar_y+22), color, -1)
            cv2.putText(img, label, (px, bar_y+19),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
        else:
            cv2.putText(img, label, (px, bar_y+19),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
        (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        px += tw + 18
    # 底部帮助
    help_txt = "LMB=draw  RMB=del-box  1-9=class  D/->=next  A/<-=prev  Z=undo  X=clr  S=jmp-susp  F=toggle  Q=quit"
    cv2.rectangle(img, (0, H-26), (W, H), (0, 0, 0), -1)
    cv2.putText(img, help_txt, (8, H-8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    return img


def load_image(img_path, xml_path):
    img = imread_unicode(img_path)
    if img is None:
        return False
    h, w = img.shape[:2]
    s = min(C.WIN_MAX / max(h, w), 1.0)
    disp = cv2.resize(img, (int(w*s), int(h*s))) if s < 1 else img.copy()
    state.img = disp
    state.scale = s
    state.img_w = w
    state.img_h = h
    state.boxes = parse_boxes(xml_path)
    return True


def save_current(img_path, xml_path):
    save_xml(xml_path, img_path.name, state.img_w, state.img_h, state.boxes)


def main():
    img_files = sorted(Path(C.IMAGES_DIR).glob('*.jpg'))
    if not img_files:
        print(f"[ERROR] no images in {C.IMAGES_DIR}")
        return

    suspicious_idx = set()
    for i, p in enumerate(img_files):
        xp = Path(C.XML_DIR) / (p.stem + '.xml')
        if xp.exists():
            try:
                root = ET.parse(xp).getroot()
                w = int(root.find('size/width').text)
                h = int(root.find('size/height').text)
                if is_suspicious(w, h, parse_boxes(xp)):
                    suspicious_idx.add(i)
            except Exception:
                suspicious_idx.add(i)
        else:
            suspicious_idx.add(i)

    print(f"Total       : {len(img_files)}")
    print(f"Suspicious  : {len(suspicious_idx)}")
    print(f"Classes     : {CLASS_NAMES}")
    print(f"View        : SUSPICIOUS only (F = toggle)")
    print()

    only_susp = True
    visible = sorted(suspicious_idx) if only_susp else list(range(len(img_files)))
    if not visible:
        visible = list(range(len(img_files)))
        only_susp = False

    cv2.namedWindow("labelfix", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("labelfix", on_mouse)

    vidx = 0
    load_image(img_files[visible[vidx]],
               Path(C.XML_DIR) / (img_files[visible[vidx]].stem + '.xml'))

    while True:
        idx = visible[vidx]
        img_path = img_files[idx]
        xml_path = Path(C.XML_DIR) / (img_path.stem + '.xml')

        disp = render(img_path.name, vidx, len(visible),
                      only_susp, len(suspicious_idx))
        cv2.imshow("labelfix", disp)
        key = cv2.waitKey(20) & 0xFF

        if key == 255:
            continue

        # 类别切换 1~9
        if ord('1') <= key <= ord('9'):
            ci = key - ord('1')
            if ci < len(CLASS_NAMES):
                state.cur_class = ci
            continue

        if key in (ord('q'), 27):
            save_current(img_path, xml_path)
            break
        elif key in (ord('d'), 83):  # next
            save_current(img_path, xml_path)
            if not is_suspicious(state.img_w, state.img_h, state.boxes):
                suspicious_idx.discard(idx)
            else:
                suspicious_idx.add(idx)
            if vidx + 1 < len(visible):
                vidx += 1
                load_image(img_files[visible[vidx]],
                           Path(C.XML_DIR) / (img_files[visible[vidx]].stem + '.xml'))
            else:
                print("Already at last image")
        elif key in (ord('a'), 81):  # prev
            save_current(img_path, xml_path)
            if not is_suspicious(state.img_w, state.img_h, state.boxes):
                suspicious_idx.discard(idx)
            else:
                suspicious_idx.add(idx)
            if vidx > 0:
                vidx -= 1
                load_image(img_files[visible[vidx]],
                           Path(C.XML_DIR) / (img_files[visible[vidx]].stem + '.xml'))
        elif key == ord('x'):
            state.boxes = []
        elif key == ord('z'):
            if state.boxes:
                state.boxes.pop()
        elif key == ord('s'):
            save_current(img_path, xml_path)
            if not is_suspicious(state.img_w, state.img_h, state.boxes):
                suspicious_idx.discard(idx)
            next_v = None
            for j in range(vidx+1, len(visible)):
                if visible[j] in suspicious_idx:
                    next_v = j
                    break
            if next_v is not None:
                vidx = next_v
                load_image(img_files[visible[vidx]],
                           Path(C.XML_DIR) / (img_files[visible[vidx]].stem + '.xml'))
            else:
                print("No more suspicious images!")
        elif key == ord('f'):
            save_current(img_path, xml_path)
            cur_global = visible[vidx]
            only_susp = not only_susp
            visible = sorted(suspicious_idx) if only_susp else list(range(len(img_files)))
            if not visible:
                visible = list(range(len(img_files)))
                only_susp = False
            vidx = 0
            for i, gi in enumerate(visible):
                if gi >= cur_global:
                    vidx = i
                    break
            load_image(img_files[visible[vidx]],
                       Path(C.XML_DIR) / (img_files[visible[vidx]].stem + '.xml'))

    cv2.destroyAllWindows()
    print(f"\nDone. Remaining suspicious: {len(suspicious_idx)}")


if __name__ == '__main__':
    main()
