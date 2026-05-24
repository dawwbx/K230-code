# 数据集清理工具
# 由 开始.bat [4] 调用，可同时清 dataset/ 和源照片
# 单独抽出来是因为 bat 处理路径太僵硬，Python 能正确读取 .last_input_dir
import os
import shutil
from pathlib import Path
import config as C


IMG_EXTS = ('*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG')


def clear_dataset():
    n_removed = 0
    if os.path.isdir(C.IMAGES_DIR):
        shutil.rmtree(C.IMAGES_DIR)
        n_removed += 1
    if os.path.isdir(C.XML_DIR):
        shutil.rmtree(C.XML_DIR)
        n_removed += 1
    labels = os.path.join(C.OUTPUT_DIR, 'labels.txt')
    if os.path.exists(labels):
        os.remove(labels)
        n_removed += 1
    return n_removed


def clear_photos(src_dir):
    n = 0
    for ext in IMG_EXTS:
        for p in Path(src_dir).glob(ext):
            try:
                p.unlink()
                n += 1
            except OSError as e:
                print(f"  [WARN] cannot delete {p.name}: {e}")
    return n


def main():
    print("What to clear?")
    print("  [1] dataset/ only (labels & cropped images)")
    print("  [2] dataset/ + source photos (originals)")
    print("  [3] cancel")
    sub = input("Choose: ").strip()
    if sub not in ('1', '2'):
        return

    target_src = None
    if sub == '2':
        target_src = C.peek_last_input_dir()
        if target_src is None:
            print("\nNo source folder remembered yet (option [1] hasn't run, "
                  "or its folder no longer exists).")
            p = input("Enter source path to clear (empty to skip photos): ").strip().strip('"').strip("'")
            if p and os.path.isdir(p):
                target_src = p
            elif p:
                print(f"  [WARN] not a directory: {p}")
        else:
            print(f"\nSource folder: {target_src}")

    print()
    print("Will clear:")
    print(f"  - dataset/  ({C.OUTPUT_DIR})")
    if target_src:
        print(f"  - photos in {target_src}")
    ok = input("\nProceed? (y/N): ").strip().lower()
    if ok != 'y':
        print("Cancelled.")
        return

    n = clear_dataset()
    print(f"dataset/ cleared ({n} items removed).")

    if target_src:
        n = clear_photos(target_src)
        print(f"{n} photos deleted from {target_src}")


if __name__ == '__main__':
    main()
