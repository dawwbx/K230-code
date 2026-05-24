# 打包脚本：把 dataset/ 压缩成 AI Cube 要求的 ZIP
# ZIP 内根目录直接是 images/、xml/、labels.txt，不能套一层 dataset/

import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import config as C

OUTPUT_ZIP = os.path.join(os.path.dirname(__file__), C.ZIP_NAME)

# AI Cube 限制
MAX_ZIP_SIZE_MB  = 200
MAX_FILE_SIZE_MB = 10


def main():
    if not os.path.isdir(C.IMAGES_DIR) or not os.path.isdir(C.XML_DIR):
        print(f"[ERROR] need both images/ and xml/ under {C.OUTPUT_DIR}")
        return

    img_files = list(Path(C.IMAGES_DIR).glob('*.jpg')) + list(Path(C.IMAGES_DIR).glob('*.png'))
    xml_files = list(Path(C.XML_DIR).glob('*.xml'))

    img_stems = {p.stem for p in img_files}
    xml_stems = {p.stem for p in xml_files}
    miss_xml  = img_stems - xml_stems
    miss_img  = xml_stems - img_stems
    if miss_xml:
        print(f"[WARN] {len(miss_xml)} images without xml (skipped)")
    if miss_img:
        print(f"[WARN] {len(miss_img)} xml without image (skipped)")

    # 完整性检查：统计每类样本数 + 空 XML 数
    valid_class = set(C.class_names())
    class_count = {n: 0 for n in valid_class}
    unknown_class = {}
    empty_xml = []
    paired = sorted(img_stems & xml_stems)
    for stem in paired:
        xp = Path(C.XML_DIR) / (stem + '.xml')
        try:
            root = ET.parse(xp).getroot()
            objs = root.findall('object')
            if not objs:
                empty_xml.append(stem)
                continue
            for o in objs:
                n = o.find('name').text
                if n in valid_class:
                    class_count[n] += 1
                else:
                    unknown_class[n] = unknown_class.get(n, 0) + 1
        except Exception:
            empty_xml.append(stem)

    print("\n--- Sanity check ---")
    print(f"Pairs           : {len(paired)}")
    print(f"Empty XML (no box): {len(empty_xml)}")
    if empty_xml[:5]:
        for s in empty_xml[:5]:
            print(f"   {s}")
        if len(empty_xml) > 5:
            print(f"   ... and {len(empty_xml)-5} more")
    for n, c in class_count.items():
        print(f"Class '{n}'     : {c} boxes")
    if unknown_class:
        print(f"[WARN] unknown class names in XML (NOT in config):")
        for n, c in unknown_class.items():
            print(f"   {n}: {c}")
        print("These will still be packed but may break training.")

    if empty_xml:
        ans = input(f"\n{len(empty_xml)} images have NO box. Pack anyway? (y/N): ").strip().lower()
        if ans != 'y':
            print("Aborted. Use labelfix to fill them in first.")
            return

    # 超大文件检查
    oversized = [(p.name, p.stat().st_size / (1024*1024))
                 for p in img_files
                 if p.stat().st_size / (1024*1024) > MAX_FILE_SIZE_MB]
    if oversized:
        print(f"\n[ERROR] {len(oversized)} files exceed {MAX_FILE_SIZE_MB}MB:")
        for n, s in oversized:
            print(f"   {n}: {s:.1f}MB")
        print("Re-run 1_auto_label.py with smaller MAX_SIZE.")
        return

    # 备份旧 ZIP
    if os.path.exists(OUTPUT_ZIP):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = OUTPUT_ZIP.replace('.zip', f'_{ts}.zip')
        os.rename(OUTPUT_ZIP, backup)
        print(f"\nOld ZIP backed up → {os.path.basename(backup)}")

    print(f"\nPacking → {OUTPUT_ZIP}")
    pair_count = 0
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for stem in paired:
            img_path = Path(C.IMAGES_DIR) / (stem + '.jpg')
            if not img_path.exists():
                img_path = Path(C.IMAGES_DIR) / (stem + '.png')
            xml_path = Path(C.XML_DIR) / (stem + '.xml')
            z.write(img_path, arcname=f"images/{img_path.name}")
            z.write(xml_path, arcname=f"xml/{xml_path.name}")
            pair_count += 1
        labels_txt = os.path.join(C.OUTPUT_DIR, 'labels.txt')
        if os.path.exists(labels_txt):
            z.write(labels_txt, arcname="labels.txt")

    zip_size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
    print("\n" + "=" * 50)
    print(f"Packed pairs : {pair_count}")
    print(f"ZIP size     : {zip_size_mb:.1f} MB")

    if zip_size_mb > MAX_ZIP_SIZE_MB:
        print(f"[ERROR] ZIP exceeds {MAX_ZIP_SIZE_MB}MB!")
        print("  - reduce MAX_SIZE in config.py (e.g. 960)")
    else:
        print(f"\nReady! Upload to AI Cube:")
        print(f"  {OUTPUT_ZIP}")


if __name__ == '__main__':
    main()
