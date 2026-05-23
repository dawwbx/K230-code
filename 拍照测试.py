# K230 摄像头 + 触摸拍照 + 相片回放
# 实时预览摄像头画面，右下角快门按钮拍照，左下角回放按钮浏览照片
# 照片存储到 /data/picture 目录
# 兼容 01Studio CanMV K230 (ST7701 800x480 + FT5316)

from machine import TOUCH
from media.display import Display
from media.sensor import Sensor
from media.media import MediaManager
import image, time, os

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

SAVE_DIR = "/data/picture"

# 快门按钮（右下角）
BTN_X = DISPLAY_WIDTH - 65
BTN_Y = DISPLAY_HEIGHT - 65
BTN_R = 45

# 回放按钮（左下角）
GALLERY_X = 55
GALLERY_Y = DISPLAY_HEIGHT - 55
GALLERY_R = 32

# 回放模式导航按钮
LEFT_X, LEFT_Y = 55, DISPLAY_HEIGHT // 2
RIGHT_X, RIGHT_Y = DISPLAY_WIDTH - 55, DISPLAY_HEIGHT // 2
BACK_X, BACK_Y = DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 55


def ensure_dir(path):
    try:
        os.listdir(path)
    except:
        os.mkdir(path)


def get_photos():
    try:
        files = os.listdir(SAVE_DIR)
        photos = [f for f in files if f.endswith('.bmp')]
        photos.sort()
        return photos
    except:
        return []


def draw_circle_btn(img, x, y, r, color, label, pressed=False):
    rr = r - 4 if pressed else r
    img.draw_circle(x, y, rr, color=color, thickness=3, fill=True)
    img.draw_circle(x, y, rr - 5, color=(255, 255, 255), thickness=1)
    w = len(label) * 8
    img.draw_string_advanced(x - w // 2, y - 8, 15, label, color=(255, 255, 255))


def draw_status_bar(img, text):
    img.draw_rectangle(0, 0, DISPLAY_WIDTH, 38, color=(0, 0, 180), fill=True)
    img.draw_string_advanced(12, 6, 18, text, color=(255, 255, 255))


def camera_mode(sensor, tp, photo_count, last_in_btn, last_in_gallery, total_cached):
    """返回 (next_mode, photo_count, total_cached)"""
    img = sensor.snapshot()

    p = tp.read(1)
    in_btn = False
    in_gallery = False
    just_saved = False

    if p:
        x, y, evt = p[0].x, p[0].y, p[0].event

        dx = x - BTN_X
        dy = y - BTN_Y
        in_btn = (dx * dx + dy * dy) <= (BTN_R * BTN_R)

        gx = x - GALLERY_X
        gy = y - GALLERY_Y
        in_gallery = (gx * gx + gy * gy) <= (GALLERY_R * GALLERY_R)

        # 快门按下 - 立即在原始画面上存盘（此时还没画任何 UI）
        if in_btn and evt == 2 and not last_in_btn:
            photo_count += 1
            ensure_dir(SAVE_DIR)
            filename = SAVE_DIR + "/photo_{:04d}.bmp".format(photo_count)
            img.save(filename)
            print("SAVED:", filename)
            total_cached += 1
            just_saved = True

        # 切换到回放模式
        if in_gallery and evt == 2 and not last_in_gallery:
            return "gallery", photo_count, total_cached

        last_in_btn = in_btn
        last_in_gallery = in_gallery

        # 只在按下事件画十字 - 某些 CanMV 固件会回报幽灵悬停/释放点，
        # 不过滤的话满屏会乱冒绿十字
        if not in_btn and not in_gallery and evt == 2:
            img.draw_cross(x, y, color=(0, 255, 0), size=10, thickness=2)
    else:
        last_in_btn = False
        last_in_gallery = False

    # 顶部状态栏
    draw_status_bar(img, "Photos: {}  |  SHOT=save  |  VIEW=gallery".format(total_cached))

    # 快门按钮
    draw_circle_btn(img, BTN_X, BTN_Y, BTN_R, (220, 30, 30), "SHOT", in_btn)
    draw_circle_btn(img, GALLERY_X, GALLERY_Y, GALLERY_R, (30, 160, 30), "VIEW", in_gallery)

    # 拍照反馈：温和的边框 + SAVED 文字，不刺眼
    if just_saved:
        img.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT,
                           color=(255, 255, 255), thickness=8, fill=False)
        img.draw_string_advanced(DISPLAY_WIDTH // 2 - 36, DISPLAY_HEIGHT // 2 - 14,
                                 28, "SAVED", color=(255, 255, 255))

    Display.show_image(img)
    return "camera", photo_count, total_cached


def gallery_mode(tp):
    """浏览已存照片，返回 'camera'"""
    photos = get_photos()

    if not photos:
        img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB565)
        img.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, color=(30, 30, 30), fill=True)
        img.draw_string_advanced(240, 200, 24, "No photos yet", color=(255, 255, 255))
        img.draw_string_advanced(200, 250, 18, "Tap anywhere to return", color=(160, 160, 160))
        Display.show_image(img)
        # 等待触摸退出，而非死等
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 1500:
            os.exitpoint()
            p = tp.read(1)
            if p and p[0].event == 2:
                break
            time.sleep_ms(30)
        return "camera"

    idx = len(photos) - 1  # 从最新的开始
    canvas = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB565)
    need_redraw = True
    last_evt_handled = False

    while True:
        os.exitpoint()

        # 只在切换照片/首次进入时重绘整张图 - 避免每帧 50ms 的加载开销
        if need_redraw:
            canvas.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                  color=(0, 0, 0), fill=True)
            try:
                photo = image.Image(SAVE_DIR + "/" + photos[idx])
                canvas.draw_image(photo, 0, 0)
            except Exception as e:
                canvas.draw_string_advanced(260, 220, 20, "Load failed: " + str(e),
                                            color=(255, 100, 100))

            # UI
            canvas.draw_rectangle(0, DISPLAY_HEIGHT - 46, DISPLAY_WIDTH, 46,
                                  color=(0, 0, 0), fill=True)
            info = "  {}/{}   {}".format(idx + 1, len(photos), photos[idx])
            canvas.draw_string_advanced(8, DISPLAY_HEIGHT - 38, 16, info, color=(255, 255, 255))

            canvas.draw_circle(LEFT_X, LEFT_Y, 28, color=(0, 100, 200), thickness=3, fill=True)
            canvas.draw_string_advanced(LEFT_X - 10, LEFT_Y - 16, 30, "<", color=(255, 255, 255))

            canvas.draw_circle(RIGHT_X, RIGHT_Y, 28, color=(0, 100, 200), thickness=3, fill=True)
            canvas.draw_string_advanced(RIGHT_X - 10, RIGHT_Y - 16, 30, ">", color=(255, 255, 255))

            canvas.draw_circle(BACK_X, BACK_Y, 40, color=(220, 100, 30), thickness=3, fill=True)
            canvas.draw_string_advanced(BACK_X - 26, BACK_Y - 12, 22, "BACK", color=(255, 255, 255))

            Display.show_image(img=canvas)
            need_redraw = False

        p = tp.read(1)
        if p:
            x, y, evt = p[0].x, p[0].y, p[0].event
            if evt == 2 and not last_evt_handled:
                last_evt_handled = True
                if ((x - LEFT_X) ** 2 + (y - LEFT_Y) ** 2) <= 900:
                    idx = (idx - 1) % len(photos)
                    need_redraw = True
                elif ((x - RIGHT_X) ** 2 + (y - RIGHT_Y) ** 2) <= 900:
                    idx = (idx + 1) % len(photos)
                    need_redraw = True
                elif ((x - BACK_X) ** 2 + (y - BACK_Y) ** 2) <= 1600:
                    return "camera"
        else:
            last_evt_handled = False

        time.sleep_ms(20)


def main():
    os.exitpoint(os.EXITPOINT_ENABLE)
    Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=False)

    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
    sensor.set_pixformat(Sensor.RGB565)

    MediaManager.init()
    sensor.run()

    tp = TOUCH(0)
    # 续编号：避免覆盖已存的照片
    existing = get_photos()
    photo_count = 0
    for f in existing:
        try:
            n = int(f.replace("photo_", "").replace(".bmp", ""))
            if n > photo_count:
                photo_count = n
        except:
            pass
    last_in_btn = False
    last_in_gallery = False
    mode = "camera"
    # 缓存照片数量，避免每帧都 listdir
    total_cached = len(existing)

    try:
        while True:
            os.exitpoint()

            if mode == "camera":
                mode, photo_count, total_cached = camera_mode(
                    sensor, tp, photo_count, last_in_btn, last_in_gallery, total_cached)
                last_in_btn = False
                last_in_gallery = False

            elif mode == "gallery":
                mode = gallery_mode(tp)
                # 从回放回到拍照时刷新计数
                total_cached = len(get_photos())

    except KeyboardInterrupt:
        print("stopped")
    except Exception as e:
        print("Error:", e)
    finally:
        sensor.stop()
        Display.deinit()
        MediaManager.deinit()


main()
