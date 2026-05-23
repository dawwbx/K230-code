# K230 摄像头 + 触摸拍照
# 屏幕上实时预览摄像头画面，右下角有虚拟快门按钮，手指点击拍照存 SD 卡
# 兼容 01Studio CanMV K230 (ST7701 800x480 + FT5316)

from machine import TOUCH
from media.display import Display
from media.sensor import Sensor
from media.media import MediaManager
import image, time, os

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

# 快门按钮参数（右下角圆形按钮）
BTN_X = DISPLAY_WIDTH - 65
BTN_Y = DISPLAY_HEIGHT - 65
BTN_R = 45

def main():
    os.exitpoint(os.EXITPOINT_ENABLE)

    # ---- 显示 ----
    Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=False)

    # ---- Sensor（单通道 RGB565，兼容 show_image）----
    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
    sensor.set_pixformat(Sensor.RGB565)

    MediaManager.init()
    sensor.run()

    tp = TOUCH(0)
    photo_count = 0
    last_in_btn = False       # 防抖：上一次是否在按钮内
    flash_timer = 0           # 拍照闪光计时器

    try:
        while True:
            os.exitpoint()
            img = sensor.snapshot()

            # ---- 顶部状态栏 ----
            img.draw_rectangle(0, 0, DISPLAY_WIDTH, 38, color=(0, 0, 180), fill=True)
            status = "Photos: {}  |  Tap red button to shoot".format(photo_count)
            img.draw_string_advanced(12, 6, 20, status, color=(255, 255, 255))

            # ---- 读取触摸 ----
            p = tp.read(1)

            if p:
                x, y, evt = p[0].x, p[0].y, p[0].event

                # 判断是否在快门按钮圆内
                dx = x - BTN_X
                dy = y - BTN_Y
                in_btn = (dx * dx + dy * dy) <= (BTN_R * BTN_R)

                if in_btn:
                    # 按钮按下效果：缩小一圈
                    r = BTN_R - 4
                else:
                    r = BTN_R

                # 按下快门（DOWN 事件 + 在按钮内 + 之前不在按钮内）
                if in_btn and evt == 2 and not last_in_btn:
                    photo_count += 1

                    # 存 SD 卡，没有就存 Flash
                    try:
                        _ = os.listdir("/sdcard")
                        filename = "/sdcard/photo_{:04d}.jpg".format(photo_count)
                    except:
                        filename = "/flash/photo_{:04d}.jpg".format(photo_count)

                    img.save(filename)
                    print("SAVED:", filename)
                    flash_timer = 6   # 触发闪光效果

                last_in_btn = in_btn

                # 不在按钮区域时画十字准星（辅助取景）
                if not in_btn:
                    img.draw_cross(x, y, color=(0, 255, 0), size=10, thickness=2)
            else:
                last_in_btn = False
                r = BTN_R

            # ---- 快门按钮 UI ----
            # 外圈（红色，按下时略缩小）
            img.draw_circle(BTN_X, BTN_Y, r, color=(220, 30, 30), thickness=4, fill=True)
            # 内圈装饰
            img.draw_circle(BTN_X, BTN_Y, r - 6, color=(255, 255, 255), thickness=2)
            img.draw_circle(BTN_X, BTN_Y, r - 10, color=(220, 30, 30), thickness=1)
            # 标签
            img.draw_string_advanced(BTN_X - 14, BTN_Y - 7, 14, "SHOT", color=(255, 255, 255))

            # ---- 闪光效果 ----
            if flash_timer > 0:
                flash_timer -= 1
                if flash_timer >= 3:
                    img.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                       color=(255, 255, 255), fill=True)

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
