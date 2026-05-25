# K230 摄像头 + 触摸拍照 + 相片回放
# 实时预览摄像头画面，右下角快门按钮拍照，左下角回放按钮浏览照片
# 照片存储到 /data/picture 目录
# 兼容 01Studio CanMV K230 (ST7701 800x480 + FT5316)

from machine import TOUCH, Pin, FPIOA
from media.display import Display
from media.sensor import Sensor
from media.media import MediaManager
import image, time, os

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

SAVE_DIR = "/data/picture"

# 01Studio K230 板载 KEY = GPIO21 (按下=低)
KEY_PIN = 21

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

# 回放模式删除按钮（右下，红色，比 BACK 小避免误触）
DEL_X, DEL_Y, DEL_R = DISPLAY_WIDTH - 60, DISPLAY_HEIGHT - 55, 32

# 删除确认弹窗
DLG_W, DLG_H = 440, 200
DLG_X = (DISPLAY_WIDTH - DLG_W) // 2
DLG_Y = (DISPLAY_HEIGHT - DLG_H) // 2
DLG_YES_X = DLG_X + 110
DLG_NO_X = DLG_X + DLG_W - 110
DLG_BTN_Y = DLG_Y + DLG_H - 45
DLG_BTN_R = 32

# 回放模式双击缩放
ZOOM_LEVELS = [1.0, 2.0, 3.0]
DOUBLE_TAP_MS = 400
DOUBLE_TAP_DIST = 40


def clamp_offset(zoom, ox, oy):
    if zoom <= 1.0:
        return 0, 0
    pw = int(DISPLAY_WIDTH * zoom)
    ph = int(DISPLAY_HEIGHT * zoom)
    ox = max(DISPLAY_WIDTH - pw, min(0, ox))
    oy = max(DISPLAY_HEIGHT - ph, min(0, oy))
    return ox, oy


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


def camera_mode(sensor, tp, key, photo_count,
                last_in_btn, last_in_gallery, last_key_pressed, total_cached):
    """返回 (next_mode, photo_count, last_key_pressed, total_cached)"""
    img = sensor.snapshot()

    # 板载 KEY 边沿检测（按下=0）
    key_pressed_now = (key is not None) and (key.value() == 0)
    key_shutter = key_pressed_now and not last_key_pressed

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

        touch_shutter = in_btn and evt == 2 and not last_in_btn

        # 切换到回放模式
        if in_gallery and evt == 2 and not last_in_gallery:
            return "gallery", photo_count, key_pressed_now, total_cached

        last_in_btn = in_btn
        last_in_gallery = in_gallery

        # 只在按下事件画十字 - 某些 CanMV 固件会回报幽灵悬停/释放点，
        # 不过滤的话满屏会乱冒绿十字
        if not in_btn and not in_gallery and evt == 2:
            img.draw_cross(x, y, color=(0, 255, 0), size=10, thickness=2)
    else:
        last_in_btn = False
        last_in_gallery = False
        touch_shutter = False

    # 触摸或 KEY 任一边沿都触发快门 - 立即在原始画面上存盘（此时还没画任何 UI）
    if touch_shutter or key_shutter:
        photo_count += 1
        ensure_dir(SAVE_DIR)
        filename = SAVE_DIR + "/photo_{:04d}.bmp".format(photo_count)
        img.save(filename)
        print("SAVED:", filename, "(KEY)" if key_shutter else "(TOUCH)")
        total_cached += 1
        just_saved = True

    # 顶部状态栏
    draw_status_bar(img, "Photos: {}  |  SHOT=save  |  VIEW=gallery".format(total_cached))

    # 快门按钮（KEY 按住时也高亮）
    draw_circle_btn(img, BTN_X, BTN_Y, BTN_R, (220, 30, 30), "SHOT", in_btn or key_pressed_now)
    draw_circle_btn(img, GALLERY_X, GALLERY_Y, GALLERY_R, (30, 160, 30), "VIEW", in_gallery)

    # 拍照反馈：温和的边框 + SAVED 文字，不刺眼
    if just_saved:
        img.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT,
                           color=(255, 255, 255), thickness=8, fill=False)
        img.draw_string_advanced(DISPLAY_WIDTH // 2 - 36, DISPLAY_HEIGHT // 2 - 14,
                                 28, "SAVED", color=(255, 255, 255))

    Display.show_image(img)
    return "camera", photo_count, key_pressed_now, total_cached


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
    confirm_delete = False  # 删除确认弹窗状态

    # 缩放/平移状态
    zoom_idx = 0
    offset_x = 0
    offset_y = 0
    last_tap_ms = 0
    last_tap_x = -999
    last_tap_y = -999
    # 拖动状态
    dragging = False
    drag_last_x = 0
    drag_last_y = 0
    drag_start_x = 0
    drag_start_y = 0
    moved = False
    # 当前照片源（用于平移时重新裁剪）
    cur_photo = None
    cur_photo_name = None

    while True:
        os.exitpoint()

        # 只在切换照片/缩放/平移时重绘 - 避免每帧 50ms 的加载开销
        if need_redraw:
            canvas.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                  color=(0, 0, 0), fill=True)
            try:
                if cur_photo_name != photos[idx]:
                    cur_photo = image.Image(SAVE_DIR + "/" + photos[idx])
                    cur_photo_name = photos[idx]

                zoom = ZOOM_LEVELS[zoom_idx]
                if zoom <= 1.0:
                    canvas.draw_image(cur_photo, 0, 0)
                else:
                    # 用 ROI 取放大后可见区域 + draw_image 的 x_scale/y_scale 拉伸到全屏
                    src_w = int(DISPLAY_WIDTH / zoom)
                    src_h = int(DISPLAY_HEIGHT / zoom)
                    src_x = int(-offset_x / zoom)
                    src_y = int(-offset_y / zoom)
                    src_x = max(0, min(DISPLAY_WIDTH - src_w, src_x))
                    src_y = max(0, min(DISPLAY_HEIGHT - src_h, src_y))
                    canvas.draw_image(cur_photo, 0, 0,
                                      x_scale=zoom, y_scale=zoom,
                                      roi=(src_x, src_y, src_w, src_h))
            except Exception as e:
                canvas.draw_string_advanced(260, 220, 20, "Load failed: " + str(e),
                                            color=(255, 100, 100))

            # UI
            canvas.draw_rectangle(0, DISPLAY_HEIGHT - 46, DISPLAY_WIDTH, 46,
                                  color=(0, 0, 0), fill=True)
            zoom_tag = "" if ZOOM_LEVELS[zoom_idx] <= 1.0 else "  [{}x]".format(int(ZOOM_LEVELS[zoom_idx]))
            info = "  {}/{}   {}{}".format(idx + 1, len(photos), photos[idx], zoom_tag)
            canvas.draw_string_advanced(8, DISPLAY_HEIGHT - 38, 16, info, color=(255, 255, 255))

            canvas.draw_circle(LEFT_X, LEFT_Y, 28, color=(0, 100, 200), thickness=3, fill=True)
            canvas.draw_string_advanced(LEFT_X - 10, LEFT_Y - 16, 30, "<", color=(255, 255, 255))

            canvas.draw_circle(RIGHT_X, RIGHT_Y, 28, color=(0, 100, 200), thickness=3, fill=True)
            canvas.draw_string_advanced(RIGHT_X - 10, RIGHT_Y - 16, 30, ">", color=(255, 255, 255))

            canvas.draw_circle(BACK_X, BACK_Y, 40, color=(220, 100, 30), thickness=3, fill=True)
            canvas.draw_string_advanced(BACK_X - 26, BACK_Y - 12, 22, "BACK", color=(255, 255, 255))

            canvas.draw_circle(DEL_X, DEL_Y, DEL_R, color=(220, 30, 30), thickness=3, fill=True)
            canvas.draw_string_advanced(DEL_X - 18, DEL_Y - 10, 18, "DEL", color=(255, 255, 255))

            # 删除确认覆盖层（modal，画在所有 UI 之上）
            if confirm_delete:
                canvas.draw_rectangle(DLG_X, DLG_Y, DLG_W, DLG_H,
                                      color=(40, 40, 40), fill=True)
                canvas.draw_rectangle(DLG_X, DLG_Y, DLG_W, DLG_H,
                                      color=(220, 30, 30), thickness=3, fill=False)
                canvas.draw_string_advanced(DLG_X + 70, DLG_Y + 22, 26,
                                            "Delete this photo?", color=(255, 255, 255))
                canvas.draw_string_advanced(DLG_X + 20, DLG_Y + 70, 18,
                                            photos[idx], color=(180, 180, 180))
                canvas.draw_circle(DLG_YES_X, DLG_BTN_Y, DLG_BTN_R,
                                   color=(220, 30, 30), thickness=3, fill=True)
                canvas.draw_string_advanced(DLG_YES_X - 24, DLG_BTN_Y - 12, 22,
                                            "YES", color=(255, 255, 255))
                canvas.draw_circle(DLG_NO_X, DLG_BTN_Y, DLG_BTN_R,
                                   color=(80, 80, 80), thickness=3, fill=True)
                canvas.draw_string_advanced(DLG_NO_X - 18, DLG_BTN_Y - 12, 22,
                                            "NO", color=(255, 255, 255))

            Display.show_image(img=canvas)
            need_redraw = False

        p = tp.read(1)
        if p:
            x, y, evt = p[0].x, p[0].y, p[0].event

            # 拖动平移：放大状态下，MOVE 事件累积位移
            if (not confirm_delete) and ZOOM_LEVELS[zoom_idx] > 1.0 and evt == 3 and dragging:
                dx = x - drag_last_x
                dy = y - drag_last_y
                if dx != 0 or dy != 0:
                    offset_x, offset_y = clamp_offset(ZOOM_LEVELS[zoom_idx],
                                                     offset_x + dx, offset_y + dy)
                    drag_last_x, drag_last_y = x, y
                    # 判定是否算作"拖动了"(超过阈值)，区分双击和拖动起手
                    if abs(x - drag_start_x) > 6 or abs(y - drag_start_y) > 6:
                        moved = True
                    need_redraw = True

            if evt == 2 and not last_evt_handled:
                last_evt_handled = True
                if confirm_delete:
                    # modal：只响应 YES / NO，点弹窗外不做任何事
                    if ((x - DLG_YES_X) ** 2 + (y - DLG_BTN_Y) ** 2) <= DLG_BTN_R * DLG_BTN_R:
                        try:
                            os.remove(SAVE_DIR + "/" + photos[idx])
                            print("DELETED:", photos[idx])
                        except Exception as e:
                            print("Delete failed:", e)
                        photos = get_photos()
                        if not photos:
                            return "camera"
                        if idx >= len(photos):
                            idx = len(photos) - 1
                        cur_photo_name = None  # 强制重载
                        zoom_idx = 0
                        offset_x = offset_y = 0
                        confirm_delete = False
                        need_redraw = True
                    elif ((x - DLG_NO_X) ** 2 + (y - DLG_BTN_Y) ** 2) <= DLG_BTN_R * DLG_BTN_R:
                        confirm_delete = False
                        need_redraw = True
                else:
                    # 优先判定按钮（在底部 UI 条区域 y >= DISPLAY_HEIGHT - 90 内才查按钮）
                    if ((x - LEFT_X) ** 2 + (y - LEFT_Y) ** 2) <= 900:
                        idx = (idx - 1) % len(photos)
                        cur_photo_name = None
                        zoom_idx = 0
                        offset_x = offset_y = 0
                        need_redraw = True
                    elif ((x - RIGHT_X) ** 2 + (y - RIGHT_Y) ** 2) <= 900:
                        idx = (idx + 1) % len(photos)
                        cur_photo_name = None
                        zoom_idx = 0
                        offset_x = offset_y = 0
                        need_redraw = True
                    elif ((x - BACK_X) ** 2 + (y - BACK_Y) ** 2) <= 1600:
                        return "camera"
                    elif ((x - DEL_X) ** 2 + (y - DEL_Y) ** 2) <= DEL_R * DEL_R:
                        confirm_delete = True
                        need_redraw = True
                    else:
                        # 图片区域按下 -> 开始拖动 + 准备判定双击
                        dragging = True
                        drag_last_x, drag_last_y = x, y
                        drag_start_x, drag_start_y = x, y
                        moved = False
        else:
            # 抬手：如果没有拖动过且距上次抬手满足双击条件，则切换缩放
            if last_evt_handled and dragging and not moved:
                now = time.ticks_ms()
                if (time.ticks_diff(now, last_tap_ms) < DOUBLE_TAP_MS and
                    abs(drag_start_x - last_tap_x) < DOUBLE_TAP_DIST and
                    abs(drag_start_y - last_tap_y) < DOUBLE_TAP_DIST):
                    # 双击：切换到下一档，以双击点为中心
                    prev_zoom = ZOOM_LEVELS[zoom_idx]
                    zoom_idx = (zoom_idx + 1) % len(ZOOM_LEVELS)
                    new_zoom = ZOOM_LEVELS[zoom_idx]
                    if new_zoom <= 1.0:
                        offset_x = offset_y = 0
                    else:
                        # 把双击点(显示坐标)在新缩放下保持在原位
                        # 原图坐标: img_px = (tap - offset) / zoom
                        # 新偏移:   new_offset = tap - img_px * new_zoom
                        img_x = (drag_start_x - offset_x) / prev_zoom
                        img_y = (drag_start_y - offset_y) / prev_zoom
                        offset_x = int(drag_start_x - img_x * new_zoom)
                        offset_y = int(drag_start_y - img_y * new_zoom)
                        offset_x, offset_y = clamp_offset(new_zoom, offset_x, offset_y)
                    last_tap_ms = 0  # 防止三连击被当成双击+双击
                    need_redraw = True
                else:
                    last_tap_ms = now
                    last_tap_x = drag_start_x
                    last_tap_y = drag_start_y
            dragging = False
            moved = False
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

    # 板载 KEY。FPIOA 复用要先设好
    fpioa = FPIOA()
    key = None
    try:
        fpioa.set_function(KEY_PIN, FPIOA.GPIO21)
        key = Pin(KEY_PIN, Pin.IN, Pin.PULL_UP)
    except Exception as e:
        print("KEY init failed:", e)

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
    last_key_pressed = False
    mode = "camera"
    # 缓存照片数量，避免每帧都 listdir
    total_cached = len(existing)

    try:
        while True:
            os.exitpoint()

            if mode == "camera":
                mode, photo_count, last_key_pressed, total_cached = camera_mode(
                    sensor, tp, key, photo_count,
                    last_in_btn, last_in_gallery, last_key_pressed, total_cached)
                last_in_btn = False
                last_in_gallery = False

            elif mode == "gallery":
                mode = gallery_mode(tp)
                # 从回放回到拍照时刷新计数
                total_cached = len(get_photos())
                last_key_pressed = (key is not None) and (key.value() == 0)

    except KeyboardInterrupt:
        print("stopped")
    except Exception as e:
        print("Error:", e)
    finally:
        sensor.stop()
        Display.deinit()
        MediaManager.deinit()


main()
