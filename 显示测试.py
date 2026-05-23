# K230 摄像头 → 800x480 ST7701 触摸屏 + CanMV IDE 同步预览
# 兼容两块板：
#   - 嘉立创 庐山派 K230 (LCKFB-LSPI-K230-1G-CanMV)
#   - 01Studio CanMV K230 (1G)
#
# 关键设计：绕开 01Studio 固件的 OSD rotate bug
#   K230 显示控制器有两类图层：
#     OSD 层    —— Display.show_image() 推送的地方，01Studio 固件这里的旋转链有 bug
#                  (OSD rotate error 2, -1 / get rotate buffer failed)
#     VIDEO 层  —— 硬件视频直通通道，独立 scaler/rotator，两块板都没问题
#   本程序用 Display.bind_layer() 把 sensor 通道直接绑到 VIDEO1，硬件 DMA
#   直送 LCD，完全不经过 OSD。IDE 预览另起一条 RGB565 通道走 compress_for_ide()。
#
# 多通道分工：
#   chn 0: YUV420SP 800x480, 硬件 DMA 直绑 VIDEO1 → LCD（零 CPU 开销）
#   chn 2: RGB565   800x480, snapshot 出 image 对象 → IDE 预览 / 未来 CV 算法
#
# 参考：
#   https://www.kendryte.com/k230_canmv/en/dev/api/mpp/K230_CanMV_Sensor_Module_API_Manual.html
#   https://www.kendryte.com/k230_canmv/en/dev/api/mpp/K230_CanMV_Display_Module_API_Manual.html

import time
import os

from media.sensor import *
from media.display import *
from media.media import *


# =========================
# 参数区
# =========================
LCD_WIDTH  = 800
LCD_HEIGHT = 480


# =========================
# 主程序
# =========================
def main():
    os.exitpoint(os.EXITPOINT_ENABLE)

    # ---- 显示初始化 ----
    # 显式传 width/height，让 panel 一开始就按 800x480 横屏配置，
    # 避免后续显示链路再做方向转换。
    Display.init(Display.ST7701, width=LCD_WIDTH, height=LCD_HEIGHT)

    # ---- sensor 通道配置 ----
    sensor = Sensor()
    sensor.reset()

    # chn 0：送 LCD 的视频通道，YUV420SP 是 K230 ISP 和显示链路的原生格式
    sensor.set_framesize(width=LCD_WIDTH, height=LCD_HEIGHT, chn=CAM_CHN_ID_0)
    sensor.set_pixformat(Sensor.YUV420SP, chn=CAM_CHN_ID_0)

    # chn 2：给 Python / IDE 预览用，RGB565 便于后续做图像处理
    sensor.set_framesize(width=LCD_WIDTH, height=LCD_HEIGHT, chn=CAM_CHN_ID_2)
    sensor.set_pixformat(Sensor.RGB565, chn=CAM_CHN_ID_2)

    # ---- 把 chn 0 直接绑到 VIDEO1 层 ----
    # 这一步是绕开 01Studio OSD rotate bug 的关键：show_image() 不再调用，
    # LCD 由硬件 DMA 自动从 chn 0 取帧刷新。
    bind_info = sensor.bind_info(x=0, y=0, chn=CAM_CHN_ID_0)
    Display.bind_layer(**bind_info, layer=Display.LAYER_VIDEO1)

    # ---- 媒体管理器 → 启动 sensor ----
    MediaManager.init()
    sensor.run()

    clock = time.clock()
    frame_cnt = 0

    try:
        while True:
            os.exitpoint()
            clock.tick()

            # LCD 由 bind_layer 自动更新，主循环只负责把帧推到 IDE
            img = sensor.snapshot(chn=CAM_CHN_ID_2)
            img.compress_for_ide()

            # 每 60 帧打印一次帧率
            frame_cnt += 1
            if frame_cnt >= 60:
                print("FPS:", clock.fps())
                frame_cnt = 0

    except KeyboardInterrupt:
        print("用户停止程序")
    except Exception as e:
        print("运行出错:", e)
    finally:
        try:
            sensor.stop()
        except:
            pass
        Display.deinit()
        MediaManager.deinit()


main()
