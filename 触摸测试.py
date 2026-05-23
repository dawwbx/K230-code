# K230 触摸屏坐标回显 — 验证触摸功能是否正常
# 兼容 01Studio CanMV K230 (ST7701 800x480 + FT5316 触摸)
#
# 注意：如果报 "OSD rotate error 2, -1"，说明 show_image 路径仍然有 bug，
# 到时切回 camera+bind_layer 方案。

from machine import TOUCH
from media.display import Display
from media.media import MediaManager
import image, time, os

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

def main():
    os.exitpoint(os.EXITPOINT_ENABLE)

    Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=False)
    MediaManager.init()

    img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB565)
    tp = TOUCH(0)

    try:
        while True:
            os.exitpoint()
            img.clear()

            # ---- 顶部标题栏 ----
            img.draw_rectangle(0, 0, DISPLAY_WIDTH, 44, color=(0, 0, 180), fill=True)
            img.draw_string_advanced(10, 8, 24, "K230 Touch Test", color=(255, 255, 255))

            # ---- 读取触摸（显式请求 5 点）----
            p = tp.read(5)

            if p:
                # 串口调试：看完整的触摸点信息
                if len(p) > 0:
                    pts_info = []
                    for pt in p:
                        pts_info.append("id={} x={} y={} evt={}".format(
                            pt.track_id, pt.x, pt.y, pt.event))
                    print("[{}] {}".format(len(p), " | ".join(pts_info)))

                for i, pt in enumerate(p):
                    x, y = pt.x, pt.y

                    # 十字准星
                    img.draw_cross(x, y, color=(0, 255, 0), size=14, thickness=2)

                    # 外圈 + 实心内圈
                    img.draw_circle(x, y, 22, color=(255, 0, 0), thickness=3)
                    img.draw_circle(x, y, 5, color=(255, 0, 0), thickness=2, fill=True)

                    # 坐标标签
                    # 坐标标签（含 track_id）
                    label = "#{} id{} ({},{})".format(i, pt.track_id, x, y)
                    img.draw_string_advanced(x + 28, y - 12, 20, label, color=(255, 255, 0))

                    # 事件类型
                    evt = pt.event
                    evt_name = "DOWN" if evt == 2 else ("MOVE" if evt == 3 else "E" + str(evt))
                    img.draw_string_advanced(x + 28, y + 10, 16, evt_name, color=(200, 200, 200))

            # ---- 底部状态栏 ----
            img.draw_rectangle(0, DISPLAY_HEIGHT - 32, DISPLAY_WIDTH, 32, color=(0, 0, 180), fill=True)
            count = len(p) if p else 0
            info = "Touch points: {}".format(count)
            img.draw_string_advanced(10, DISPLAY_HEIGHT - 26, 18, info, color=(255, 255, 255))

            Display.show_image(img)
            time.sleep_ms(30)

    except KeyboardInterrupt:
        print("stopped")
    except Exception as e:
        print("Error:", e)
    finally:
        Display.deinit()
        MediaManager.deinit()

main()
