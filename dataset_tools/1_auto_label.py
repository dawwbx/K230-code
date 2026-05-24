# 自动标注：HSV 颜色阈值 + 轮廓 → Pascal VOC XML
# 输入：config.INPUT_DIR 下所有图片
# 输出：dataset/images/*.jpg + dataset/xml/*.xml + dataset/labels.txt
# 支持多类别（在 config.CLASSES 里加 dict 即可）

import cv2
import numpy as np
import os
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import config as C


# ---- I/O helpers ----
def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite_unicode(path, img, quality=92):
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        buf.tofile(path)
    return ok


def resize_image(img, max_size):
    h, w = img.shape[:2]
    if max(h, w) <= max_size:
        return img
    s = max_size / max(h, w)
    return cv2.resize(img, (int(w*s), int(h*s)), interpolation=cv2.INTER_AREA)


# ---- VOC XML ----
def make_voc_xml(filename, w, h, labeled_boxes):
    """labeled_boxes: list of (class_name, x1, y1, x2, y2)"""
    root = Element('annotation')
    SubElement(root, 'folder').text = 'images'
    SubElement(root, 'filename').text = filename
    size = SubElement(root, 'size')
    SubElement(size, 'width').text  = str(w)
    SubElement(size, 'height').text = str(h)
    SubElement(size, 'depth').text  = '3'
    SubElement(root, 'segmented').text = '0'
    for name, x1, y1, x2, y2 in labeled_boxes:
        obj = SubElement(root, 'object')
        SubElement(obj, 'name').text = name
        SubElement(obj, 'pose').text = 'Unspecified'
        SubElement(obj, 'truncated').text = '0'
        SubElement(obj, 'difficult').text = '0'
        bnd = SubElement(obj, 'bndbox')
        SubElement(bnd, 'xmin').text = str(int(x1))
        SubElement(bnd, 'ymin').text = str(int(y1))
        SubElement(bnd, 'xmax').text = str(int(x2))
        SubElement(bnd, 'ymax').text = str(int(y2))
    return minidom.parseString(tostring(root)).toprettyxml(indent="  ")


# ---- 单类别的检测 ----
def detect_one_class(img_bgr, cls):
    h, w = img_bgr.shape[:2]
    area_total = h * w

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, cls["hsv_lower"], cls["hsv_upper"])
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (cls["kernel"], cls["kernel"]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < cls["min_ratio"] * area_total or area > cls["max_ratio"] * area_total:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        aspect = max(bw, bh) / max(1, min(bw, bh))
        if aspect > 3.5:
            continue
        cands.append((area, x, y, bw, bh))

    if not cands:
        return []

    cands.sort(reverse=True)
    if not cls["multi_boxes"]:
        cands = cands[:1]

    out = []
    for _, x, y, bw, bh in cands:
        x1 = max(0, x - C.BOX_PADDING)
        y1 = max(0, y - C.BOX_PADDING)
        x2 = min(w, x + bw + C.BOX_PADDING)
        y2 = min(h, y + bh + C.BOX_PADDING)
        out.append((cls["name"], x1, y1, x2, y2))
    return out


def main():
    os.makedirs(C.IMAGES_DIR, exist_ok=True)
    os.makedirs(C.XML_DIR, exist_ok=True)

    # labels.txt
    with open(os.path.join(C.OUTPUT_DIR, 'labels.txt'), 'w', encoding='utf-8') as f:
        for name in C.class_names():
            f.write(name + '\n')

    files = []
    for ext in ('*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG'):
        files.extend(Path(C.INPUT_DIR).glob(ext))
    files = sorted(set(files))

    if not files:
        print(f"[ERROR] no images in {C.INPUT_DIR}")
        return

    print(f"Found {len(files)} images. Classes: {C.class_names()}")
    print()

    ok_cnt, empty_cnt = 0, 0
    empty_list = []

    for i, p in enumerate(files):
        img = imread_unicode(p)
        if img is None:
            print(f"[SKIP] cannot read: {p.name}")
            continue

        img = resize_image(img, C.MAX_SIZE)
        h, w = img.shape[:2]

        boxes = []
        for cls in C.CLASSES:
            boxes.extend(detect_one_class(img, cls))

        out_name = f"img_{i+1:04d}.jpg"
        xml_name = f"img_{i+1:04d}.xml"
        imwrite_unicode(os.path.join(C.IMAGES_DIR, out_name), img)
        xml_str = make_voc_xml(out_name, w, h, boxes)
        with open(os.path.join(C.XML_DIR, xml_name), 'w', encoding='utf-8') as f:
            f.write(xml_str)

        if boxes:
            ok_cnt += 1
            tags = ",".join(b[0] for b in boxes)
            print(f"[OK]   {p.name:35s} -> {out_name}  [{len(boxes)}: {tags}]")
        else:
            empty_cnt += 1
            empty_list.append((p.name, out_name))
            print(f"[WARN] {p.name:35s} -> {out_name}  NO BOX")

    print("\n" + "=" * 50)
    print(f"Total          : {len(files)}")
    print(f"Auto-labeled   : {ok_cnt}")
    print(f"Empty (todo)   : {empty_cnt}")
    if empty_list:
        print("\nNeed manual labeling:")
        for orig, new in empty_list:
            print(f"  {orig}  ->  {new}")
    print(f"\nOutput         : {C.OUTPUT_DIR}")
    print("Next           : run labelfix to review & fix")


if __name__ == '__main__':
    main()
