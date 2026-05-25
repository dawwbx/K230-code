# K230 触摸视觉学习项目

基于 **01Studio CanMV K230** + **800×480 ST7701 触摸屏** 的视觉与触摸交互实验集合。

## 硬件

- **板子**：01Studio CanMV K230 - 1G（亦兼容嘉立创庐山派）
- **屏幕**：800×480 ST7701 MIPI LCD，FT5316 电容触摸（最多 5 点）
- **摄像头**：GC2093 (1920×1080@60)

## 程序列表

| 文件 | 功能 |
|---|---|
| `显示测试.py` | 摄像头 → LCD + CanMV IDE 同步预览（`bind_layer` 路径） |
| `触摸测试.py` | 多点触摸坐标实时显示（验证触摸屏好坏） |
| `拍照测试.py` | 摄像头预览 + 虚拟快门按钮触摸拍照 |
| `找蓝色物体.py` | LAB 色块检测 + 6 个 +/- 按钮调阈值，自动存盘 |
| `找圆形测试.py` | 霍夫圆检测（320×240 加速）+ 3 个参数可调 |
| `AI测试.py` | 加载预训练 YOLOv8n（COCO 80 类）实时推理 |
| `det_uart.py` | **通用串口模块**：检测目标中心点 → UART2 发送，跨模型复用 |
| `dataset_tools/` | 自定义训练数据流水线：拍照 → HSV 自动标 → 手动修正 → 打包上传 AI Cube |

## det_uart.py 串口模块

把检测脚本得到的目标中心点通过 01Studio 板背面 **XH-1.25mm-4P** 座子（UART2，GPIO11=TX2，GPIO12=RX2，3.3V 电平）发出去。

**部署**：放到 `/sdcard/` **根目录**（K230 默认 `sys.path` 只含 `/sdcard/`，放子目录里 import 会失败）。

**用法**：

```python
from det_uart import DetUart

du = DetUart(display_size, rgb888p_size, baudrate=115200, debug=False)

while True:
    img = pl.get_frame()
    res = det_app.run(img)
    det_app.draw_result(pl.osd_img, res)
    du.process(res, pl.osd_img)        # 一行：提取中心点 + 画十字 + 串口发送
    pl.show_image()
```

**帧格式**（每目标 8 字节，大端）：

```
0x55 | id(1B) | cx(2B BE) | cy(2B BE) | count(1B) | 0x66
```

- `id`：从 1 起，画面**最左目标 = 1 号**
- `cx/cy`：显示坐标系
- `count`：当前帧目标总数
- 无检测时不发送

**接线**（USB-TTL 调试）：模块 RX ↔ 座子 TX2、GND ↔ GND，不要接 5V。

## 关键技术坑

1. **不要用 `Display.show_image()` 走摄像头主路径** — 01Studio 固件 OSD rotate bug 会让程序崩溃。改用 `Display.bind_layer()` 直绑 VIDEO1 层。
2. **不要跨板烧固件** — 庐山派和 01Studio 的 panel/触摸/电源时序硬编码，跨刷可能烧屏。
3. **`Sensor.FHD` 隐式绑定 YUV420SP**，想用 RGB565 要显式 `set_framesize(width=W, height=H)`。
4. **`find_circles()` 在 800×480 只有 ~1 FPS**，必须降到 320×240 检测，结果按比例画到屏幕。
5. **配置存盘优先 SD 卡** — `/flash` 在某些固件写入会 `[Errno 22] EINVAL`。
6. **AI 推理时框对不上实物** — `RGB888P_SIZE` 必须和显示纵横比一致（如 800×480 = 5:3，则推理通道用 640×384），否则坐标线性映射会错位。
7. **自定义模块要放 `/sdcard/` 根目录** — K230 默认 `sys.path` 不递归含子目录，放 `/sdcard/mp_deployment_source/` 里 import 会 `ImportError`。

## 运行方式

1. 在 CanMV IDE 中打开 `.py` 文件
2. 连接 K230 板（USB 串口）
3. 点击运行按钮

阈值配置会自动保存到 `/sdcard/*.cfg`（重新运行时自动加载）。
