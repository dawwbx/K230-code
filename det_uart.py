# -*- coding: utf-8 -*-
# K230 检测目标中心点串口发送模块
# 板子背面 XH-1.25mm-4P 座子 = UART2 (GPIO11=TX2, GPIO12=RX2)
#
# 帧格式（每目标 8 字节，大端）:
#   0x55 | id(1B) | cx(2B) | cy(2B) | count(1B) | 0x66
#
# 用法:
#   from det_uart import DetUart
#   du = DetUart(display_size, rgb888p_size)            # 初始化一次
#   du.process(res, pl.osd_img)                         # 每帧调用一次

from machine import UART, FPIOA
import struct


class DetUart:
    def __init__(self, display_size, rgb888p_size,
                 baudrate=115200, draw=True, debug=False,
                 cross_color=(255, 0, 0), text_color=(255, 255, 0)):
        """
        display_size:  [w, h] 显示分辨率
        rgb888p_size:  [w, h] AI 通道分辨率
        baudrate:      串口波特率
        draw:          是否在 osd_img 上画十字 + 编号
        debug:         是否在控制台打印发送的字节
        """
        fpioa = FPIOA()
        fpioa.set_function(11, FPIOA.UART2_TXD)
        fpioa.set_function(12, FPIOA.UART2_RXD)
        self.uart = UART(UART.UART2, baudrate)

        self.dw = int(display_size[0])
        self.dh = int(display_size[1])
        self.rw = int(rgb888p_size[0])
        self.rh = int(rgb888p_size[1])

        self.draw = draw
        self.debug = debug
        self.cross_color = cross_color
        self.text_color = text_color

    def _extract_boxes(self, res):
        """兼容多种检测结果格式，返回统一的 [x1,y1,x2,y2] 列表"""
        if not res:
            return []
        # AI Cube DetectionApp: {'scores':[], 'idx':[], 'boxes':[[x1,y1,x2,y2],...]}
        if isinstance(res, dict):
            return res.get('boxes') or []
        # 旧式: [[class_id, conf, x1, y1, x2, y2], ...]
        out = []
        for b in res:
            if len(b) >= 6:
                out.append([b[2], b[3], b[4], b[5]])
            elif len(b) >= 4:
                out.append([b[0], b[1], b[2], b[3]])
        return out

    def _compute_centers(self, boxes):
        """返回显示坐标系下的中心点列表，按 x 升序（最左 = 1 号）"""
        centers = []
        for box in boxes:
            x1 = int(box[0]); y1 = int(box[1])
            x2 = int(box[2]); y2 = int(box[3])
            cx = (x1 + x2) * self.dw // (2 * self.rw)
            cy = (y1 + y2) * self.dh // (2 * self.rh)
            centers.append((cx, cy))
        centers.sort(key=lambda p: p[0])
        return centers

    def _draw(self, osd_img, centers):
        if osd_img is None:
            return
        for i, (cx, cy) in enumerate(centers, start=1):
            osd_img.draw_cross(cx, cy, color=self.cross_color, size=10, thickness=2)
            label = "{}:({},{})".format(i, cx, cy)
            osd_img.draw_string_advanced(cx + 12, cy - 24, 16, label,
                                         color=self.text_color)

    def _send(self, centers):
        count = len(centers)
        for i, (cx, cy) in enumerate(centers, start=1):
            cx_c = max(0, min(0xFFFF, cx))
            cy_c = max(0, min(0xFFFF, cy))
            frame = struct.pack('>BBHHBB', 0x55, i, cx_c, cy_c, count, 0x66)
            self.uart.write(frame)
            if self.debug:
                print("UART TX:", " ".join("{:02X}".format(b) for b in frame),
                      "| id={} x={} y={} cnt={}".format(i, cx, cy, count))

    def process(self, res, osd_img=None):
        """
        一站式处理：从检测结果到绘制+发送。
        res:     检测结果（字典 或 列表）
        osd_img: 用于绘制的 OSD 图层（None 则不画）
        返回:    中心点列表 [(cx, cy), ...]，按 x 升序
        """
        boxes = self._extract_boxes(res)
        if not boxes:
            return []
        centers = self._compute_centers(boxes)
        if self.draw and osd_img is not None:
            self._draw(osd_img, centers)
        self._send(centers)
        return centers
