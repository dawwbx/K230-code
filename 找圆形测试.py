# K230 圆形检测 v2 — 低分辨率 find_circles + 屏幕坐标缩放
# 思路：在 320x240 低分辨率上跑 Hough 圆检测（CPU 负担小），
# 把检测结果按比例放大到 800x480 屏幕上画框
# 不依赖颜色，适合杂乱环境
# 兼容 01Studio CanMV K230 (ST7701 800x480 + FT5316)

from machine import TOUCH
from media.display import Display
from media.sensor import Sensor
from media.media import MediaManager
import image, time, os

# ---- 显示尺寸 ----
DISPLAY_W = 800
DISPLAY_H = 480

# ---- sensor 分辨率：低分辨率跑霍夫检测，速度才提得起来 ----
DETECT_W = 320
DETECT_H = 240

# 缩放系数（从检测分辨率映射到显示分辨率）
SCALE_X = DISPLAY_W / DETECT_W
SCALE_Y = DISPLAY_H / DETECT_H

# ---- 布局 ----
PREVIEW_H = 350
BTN_TOP = PREVIEW_H
BTN_H = DISPLAY_H - BTN_TOP
ROW1_Y = BTN_TOP + 20
ROW2_Y = BTN_TOP + 54
ROW3_Y = BTN_TOP + 88
BTN_BTN_H = 28

# ---- 可调参数（基于检测分辨率 320x240）----
# [标签, 当前值, 最小值, 最大值, 步长]
DEFAULTS = [
    ["Thr", 2500,  500, 6000,  200],     # 霍夫圆灵敏度：越高越严格
    ["Rlo",   15,    5,  100,    5],     # 最小半径 (检测分辨率)
    ["Rhi",   60,   10,  120,    5],     # 最大半径 (检测分辨率)
]
params = [row[:] for row in DEFAULTS]

CONFIG_PATH = None
saved_flag = 0
_dbg_cnt = 0

# ====================== 存储 ======================

def _detect_config_path():
    try:
        os.listdir("/sdcard")
        return "/sdcard/circle_hough.cfg"
    except:
        return "/flash/circle_hough.cfg"

def load_thresholds():
    try:
        with open(CONFIG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = int(val)
                    for p in params:
                        if p[0] == key:
                            p[1] = max(p[2], min(p[3], val))
                            break
        print("Loaded:", CONFIG_PATH)
    except:
        print("No saved thresholds, using defaults")

def save_thresholds():
    global saved_flag
    try:
        with open(CONFIG_PATH, "w") as f:
            for p in params:
                f.write("{}={}\n".format(p[0], p[1]))
        saved_flag = 40
        print("Saved:", CONFIG_PATH)
    except Exception as e:
        print("Save failed:", e)

# ====================== 触摸 ======================

def handle_touch(x, y, evt):
    if evt != 2:
        return
    if y < BTN_TOP:
        return

    col_w = DISPLAY_W // 3
    col = x // col_w
    if col >= 3:
        col = 2

    name, val, vmin, vmax, step = params[col]

    if ROW2_Y <= y < ROW2_Y + BTN_BTN_H:
        new_val = max(vmin, val - step)
        if new_val != val:
            params[col][1] = new_val
            save_thresholds()
    elif ROW3_Y <= y < ROW3_Y + BTN_BTN_H:
        new_val = min(vmax, val + step)
        if new_val != val:
            params[col][1] = new_val
            save_thresholds()

# ====================== UI ======================

def draw_ui(img, n_found, fps):
    global saved_flag

    img.draw_rectangle(0, PREVIEW_H, DISPLAY_W, 2, color=(60, 60, 60), fill=True)
    img.draw_rectangle(0, BTN_TOP, DISPLAY_W, BTN_H, color=(40, 40, 40), fill=True)

    col_w = DISPLAY_W // 3

    for i in range(3):
        name, val, vmin, vmax, step = params[i]
        x0 = i * col_w
        xc = x0 + col_w // 2

        if i > 0:
            img.draw_line(x0, BTN_TOP, x0, DISPLAY_H, color=(80, 80, 80))

        label = "{}={}".format(name, val)
        img.draw_string_advanced(x0 + 10, ROW1_Y, 18, label, color=(255, 255, 255))

        bx = x0 + 30
        bw = col_w - 60
        img.draw_rectangle(bx, ROW2_Y, bw, BTN_BTN_H, color=(120, 50, 50), fill=True)
        img.draw_string_advanced(xc - 4, ROW2_Y + 3, 18, "-", color=(255, 255, 255))

        img.draw_rectangle(bx, ROW3_Y, bw, BTN_BTN_H, color=(50, 120, 50), fill=True)
        img.draw_string_advanced(xc - 4, ROW3_Y + 3, 18, "+", color=(255, 255, 255))

    img.draw_string_advanced(6, 6, 18,
                             "Circles: {}".format(n_found), color=(0, 255, 0))
    img.draw_string_advanced(DISPLAY_W - 100, 6, 18,
                             "FPS:{:.1f}".format(fps), color=(255, 255, 0))

    if saved_flag > 0:
        img.draw_string_advanced(6, 28, 14, "SAVED!", color=(0, 255, 0))

# ====================== 主程序 ======================

def main():
    global saved_flag, CONFIG_PATH, _dbg_cnt
    os.exitpoint(os.EXITPOINT_ENABLE)

    CONFIG_PATH = _detect_config_path()

    Display.init(Display.ST7701, width=DISPLAY_W, height=DISPLAY_H, to_ide=False)

    sensor = Sensor()
    sensor.reset()
    # 直接出低分辨率，省得后期 resize
    sensor.set_framesize(width=DETECT_W, height=DETECT_H)
    sensor.set_pixformat(Sensor.RGB565)

    MediaManager.init()
    sensor.run()

    tp = TOUCH(0)
    load_thresholds()

    clock = time.clock()

    try:
        while True:
            os.exitpoint()
            clock.tick()

            # ---- 拿低分辨率小图做检测 ----
            small = sensor.snapshot()    # 320x240

            thr = params[0][1]
            rlo = params[1][1]
            rhi = params[2][1]

            circles = small.find_circles(threshold=thr,
                                         x_margin=10, y_margin=10, r_margin=10,
                                         r_min=rlo, r_max=rhi, r_step=2)

            # ---- 创建大画布（800x480）并把小图放大上去 ----
            # 用 image.Image 拼装显示帧
            disp = image.Image(DISPLAY_W, DISPLAY_H, image.RGB565)
            # 把 320x240 小图缩放到 800x350 预览区
            disp.draw_image(small, 0, 0,
                            x_scale=DISPLAY_W / DETECT_W,
                            y_scale=PREVIEW_H / DETECT_H)

            # ---- 把检测到的圆按比例放大画在 disp 上 ----
            preview_sy = PREVIEW_H / DETECT_H
            found = 0
            if circles:
                for c in circles:
                    cx = int(c.x() * SCALE_X)
                    cy = int(c.y() * preview_sy)
                    r = int(c.r() * SCALE_X)
                    if cy + r > PREVIEW_H:
                        continue
                    found += 1
                    disp.draw_circle(cx, cy, r, color=(0, 255, 0), thickness=3)
                    disp.draw_cross(cx, cy, color=(255, 0, 0), size=8, thickness=2)
                    disp.draw_string_advanced(cx + r + 4, cy - 8, 14,
                                              "r={}".format(c.r()),
                                              color=(255, 255, 255))

            # ---- UI ----
            draw_ui(disp, found, clock.fps())

            # ---- 触摸 ----
            p = tp.read(1)
            if p:
                handle_touch(p[0].x, p[0].y, p[0].event)

            # ---- 调试打印 ----
            _dbg_cnt += 1
            if _dbg_cnt >= 30:
                _dbg_cnt = 0
                n = len(circles) if circles else 0
                print("circles={}  fps={:.1f}".format(n, clock.fps()))

            if saved_flag > 0:
                saved_flag -= 1

            Display.show_image(disp)

    except KeyboardInterrupt:
        print("stopped")
    except Exception as e:
        print("Error:", e)
    finally:
        sensor.stop()
        Display.deinit()
        MediaManager.deinit()

main()
