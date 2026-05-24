# K230 AI 测试：YOLOv8n 80 类目标检测（COCO 数据集）
# 使用新版固件提供的高层 libs.YOLO.YOLOv8 类，
# 内部已封装完整的 preprocess + inference + postprocess + draw，
# 不再依赖旧固件的 aidemo.ob_det_post_process（新固件已移除）。
#
# 模型下载：
#   https://www.kendryte.com/zh/ModelDetail?id=53
#   文件名：yolov8n_640.kmodel
#   放置：/sdcard/examples/kmodel/yolov8n_640.kmodel
#
# 参考：
#   https://www.kendryte.com/k230_canmv/zh/main/api/aidemo/YOLO_Module_API_Manual.html

from libs.PipeLine import PipeLine, ScopedTiming
from libs.YOLO import YOLOv8

import os, gc, sys, time


# =========================
# 参数区
# =========================
DISPLAY_MODE = "lcd"                       # "lcd"=800x480 ST7701, "hdmi"=1920x1080
DISPLAY_SIZE = [800, 480] if DISPLAY_MODE == "lcd" else [1920, 1080]

KMODEL_PATH  = "/sdcard/examples/kmodel/yolov8n_640.kmodel"
MODEL_INPUT  = [640, 640]                  # 模型输入尺寸
# AI 通道分辨率：必须和 DISPLAY_SIZE 同长宽比，否则检测框会偏移/放大！
# 800x480 = 5:3，所以这里用 640x384（也是 5:3，且 16 对齐）
RGB888P_SIZE = [640, 384]

CONF_THRES   = 0.35                        # 置信度阈值（0.5 太严会漏小目标，0.35 较平衡）
NMS_THRES    = 0.45                        # NMS IoU 阈值
MAX_BOXES    = 50                          # 单帧最大检测框数

# COCO 80 类标签
LABELS = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck",
    "boat","traffic light","fire hydrant","stop sign","parking meter","bench",
    "bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe",
    "backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard",
    "sports ball","kite","baseball bat","baseball glove","skateboard","surfboard",
    "tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl",
    "banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza",
    "donut","cake","chair","couch","potted plant","bed","dining table","toilet",
    "tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven",
    "toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear",
    "hair drier","toothbrush"
]


# =========================
# 主程序
# =========================
if __name__ == "__main__":
    os.exitpoint(os.EXITPOINT_ENABLE)

    # PipeLine 一键搞定 sensor + display + OSD
    pl = PipeLine(rgb888p_size=RGB888P_SIZE,
                  display_size=DISPLAY_SIZE,
                  display_mode=DISPLAY_MODE)
    pl.create()

    # 高层 YOLOv8 实例 —— 内部已封装 preprocess / inference / postprocess / draw
    yolo = YOLOv8(task_type="detect",
                  mode="video",
                  kmodel_path=KMODEL_PATH,
                  labels=LABELS,
                  rgb888p_size=RGB888P_SIZE,
                  model_input_size=MODEL_INPUT,
                  conf_thresh=CONF_THRES,
                  nms_thresh=NMS_THRES,
                  max_boxes_num=MAX_BOXES,
                  debug_mode=0)
    yolo.config_preprocess()

    print("YOLOv8n 80-class detector ready. Press Ctrl+C to stop.")

    try:
        while True:
            os.exitpoint()
            with ScopedTiming("total", 1):
                img = pl.get_frame()              # 从 chn 2 拿一帧 RGB888P
                res = yolo.run(img)               # preprocess + inference + postprocess
                yolo.draw_result(res, pl.osd_img) # 画到 OSD 透明层
                pl.show_image()
                gc.collect()
    except KeyboardInterrupt:
        print("stopped by user")
    except Exception as e:
        print("error:", e)
        sys.print_exception(e)
    finally:
        yolo.deinit()
        pl.destroy()
