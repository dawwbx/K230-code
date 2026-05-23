# K230 蓝色物体检测 + 触摸可调阈值
# 屏幕上方显示摄像头画面（检测到的蓝色物体描边），下方是 6 个阈值调节按钮
# 电赛色块追踪场景适用
# 兼容 01Studio CanMV K230 (ST7701 800x480 + FT5316)

from machine import TOUCH
from media.display import Display
from media.sensor import Sensor
from media.media import MediaManager
import image, time, os

DISPLAY_W = 800
DISPLAY_H = 480

# ---- 预览区域 ----
PREVIEW_H = 350                         # 预览区高度（顶部）

# ---- 按钮区域 ----
BTN_TOP = PREVIEW_H                     # 按钮区起始 Y
BTN_H = DISPLAY_H - BTN_TOP             # 按钮区高度 = 130px
BTN_COL_W = DISPLAY_W // 6              # 每列宽度 ~133px
ROW1_Y = BTN_TOP + 20                   # 标签+数值行
ROW2_Y = BTN_TOP + 54                   # [-] 按钮行
ROW3_Y = BTN_TOP + 88                   # [+] 按钮行
BTN_BTN_H = 28                          # 单个按钮高度

# ---- LAB 阈值参数 ----
# [标签, 当前值, 最小值, 最大值, 步长]
DEFAULTS = [
    ["L_lo",   0,   0, 100,   5],
    ["L_hi", 100,   0, 100,   5],
    ["A_lo", -80, -128, 127,  10],
    ["A_hi",  20, -128, 127,  10],
    ["B_lo", -80, -128, 127,  10],
    ["B_hi", -10, -128, 127,  10],
]
params = [row[:] for row in DEFAULTS]   # 深拷贝，运行时可修改

CONFIG_PATH = None   # 运行时根据实际可用路径决定
saved_flag = 0       # >0 时在 UI 上显示 "SAVED"

def _detect_config_path():
    """选择可写的存储路径：优先 SD 卡，不行再 Flash"""
    try:
        os.listdir("/sdcard")
        return "/sdcard/blue_thresh.cfg"
    except:
        return "/flash/blue_thresh.cfg"

def get_thresholds():
    """从 params 列表提取当前 6 个阈值"""
    return (params[0][1], params[1][1],
            params[2][1], params[3][1],
            params[4][1], params[5][1])

def load_thresholds():
    """从 Flash 加载之前保存的阈值，失败则用默认值"""
    global saved_flag
    try:
        with open(CONFIG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = int(val)
                    for p in params:
                        if p[0] == key:
                            # 限制在合法范围
                            p[1] = max(p[2], min(p[3], val))
                            break
        print("Loaded thresholds from", CONFIG_PATH)
    except:
        print("No saved thresholds, using defaults")

def save_thresholds():
    """将当前阈值写入 Flash"""
    global saved_flag
    try:
        with open(CONFIG_PATH, "w") as f:
            for p in params:
                f.write("{}={}\n".format(p[0], p[1]))
        saved_flag = 40  # 约 1 秒显示 "SAVED"
        print("Thresholds saved to", CONFIG_PATH)
    except Exception as e:
        print("Save failed:", e)

def handle_button_touch(x, y):
    """判断触摸点属于哪个按钮，执行对应的增减操作。
    返回 True 表示点击了按钮（已处理），False 表示点在预览区。"""
    if y < BTN_TOP:
        return False

    col = x // BTN_COL_W
    if col >= 6:
        col = 5

    name, val, vmin, vmax, step = params[col]

    if ROW2_Y <= y < ROW2_Y + BTN_BTN_H:
        # 按了 [-]
        new_val = max(vmin, val - step)
        if new_val != val:
            params[col][1] = new_val
            save_thresholds()
        return True
    elif ROW3_Y <= y < ROW3_Y + BTN_BTN_H:
        # 按了 [+]
        new_val = min(vmax, val + step)
        if new_val != val:
            params[col][1] = new_val
            save_thresholds()
        return True

    return False  # 点在按钮区的空白处

def draw_ui(img, blobs):
    """在图像上叠加预览框 + 按钮 UI + 检测结果"""

    # ---- 预览区边框（半透明不可用，画线代替）----
    img.draw_rectangle(0, PREVIEW_H, DISPLAY_W, 2, color=(60, 60, 60), fill=True)

    # ---- 按钮区背景 ----
    img.draw_rectangle(0, BTN_TOP, DISPLAY_W, BTN_H, color=(40, 40, 40), fill=True)

    for i in range(6):
        name, val, vmin, vmax, step = params[i]
        x0 = i * BTN_COL_W
        xc = x0 + BTN_COL_W // 2

        # 列分隔线
        if i > 0:
            img.draw_line(x0, BTN_TOP, x0, DISPLAY_H, color=(80, 80, 80))

        # 参数名 + 当前值
        label = "{}={}".format(name, val)
        img.draw_string_advanced(x0 + 6, ROW1_Y, 15, label, color=(255, 255, 255))

        # [-] 按钮
        bx = x0 + 14
        bw = BTN_COL_W - 28
        img.draw_rectangle(bx, ROW2_Y, bw, BTN_BTN_H, color=(120, 50, 50), fill=True)
        img.draw_string_advanced(xc - 4, ROW2_Y + 3, 18, "-", color=(255, 255, 255))

        # [+] 按钮
        img.draw_rectangle(bx, ROW3_Y, bw, BTN_BTN_H, color=(50, 120, 50), fill=True)
        img.draw_string_advanced(xc - 4, ROW3_Y + 3, 18, "+", color=(255, 255, 255))

    # ---- 检测结果统计 ----
    global saved_flag
    info = "Blobs: {}".format(len(blobs))
    img.draw_string_advanced(DISPLAY_W - 110, 6, 18, info, color=(0, 255, 0))

    # 保存提示
    if saved_flag > 0:
        img.draw_string_advanced(DISPLAY_W - 110, 28, 14, "SAVED!", color=(0, 255, 0))

    # 当前阈值摘要
    t = get_thresholds()
    summary = "L[{},{}] A[{},{}] B[{},{}]".format(*t)
    img.draw_string_advanced(6, 6, 15, summary, color=(255, 255, 0))


def main():
    global saved_flag, CONFIG_PATH
    os.exitpoint(os.EXITPOINT_ENABLE)

    CONFIG_PATH = _detect_config_path()

    Display.init(Display.ST7701, width=DISPLAY_W, height=DISPLAY_H, to_ide=False)

    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=DISPLAY_W, height=DISPLAY_H)
    sensor.set_pixformat(Sensor.RGB565)

    MediaManager.init()
    sensor.run()

    tp = TOUCH(0)
    load_thresholds()
    print("Current thresholds:", get_thresholds())

    try:
        while True:
            os.exitpoint()
            img = sensor.snapshot()

            # .... 色块检测 ....
            thresholds = get_thresholds()
            blobs = img.find_blobs([thresholds], pixels_threshold=200,
                                   area_threshold=200, merge=True)

            # .... 给检测到的色块描边 ....
            for b in blobs:
                # 矩形框
                img.draw_rectangle(b.rect(), color=(0, 255, 0), thickness=2)
                # 十字准星在中心
                img.draw_cross(b.cx(), b.cy(), color=(255, 0, 0), size=8, thickness=2)
                # 面积标签
                img.draw_string_advanced(b.x(), b.y() - 14, 13,
                                         str(b.area()), color=(255, 255, 255))

            # .... 叠加 UI ....
            draw_ui(img, blobs)

            # .... 处理触摸 ....
            p = tp.read(1)
            if p:
                x, y, evt = p[0].x, p[0].y, p[0].event
                if evt == 2:  # DOWN 事件才响应，避免按住时连续触发
                    handle_button_touch(x, y)

            # ---- "SAVED" 动画倒计时 ----
            if saved_flag > 0:
                saved_flag -= 1

            Display.show_image(img)
            time.sleep_ms(30)

    except KeyboardInterrupt:
        print("stopped")
    except Exception as e:
        print("Error:", e)
    finally:
        sensor.stop()
        Display.deinit()
        MediaManager.deinit()

main()
