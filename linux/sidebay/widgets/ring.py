"""cairo 自绘环形仪表：分段圆弧插值模拟角度渐变 + 发光。"""

from math import tau

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


def ring_segment_colors(base: tuple[float, float, float, float], n: int) -> list[tuple[float, float, float, float]]:
    """从 base 亮度 40% 渐变到满亮，n 段颜色。"""
    if n <= 1:
        return [base]
    return [
        tuple(min(c * (0.4 + 0.6 * i / (n - 1)), 1.0) for c in base[:3]) + (base[3],)
        for i in range(n)
    ]


def ring_arc_end(value: float) -> float:
    """value 对应的弧终点角度：从顶部（-tau/4）起按 value/100 比例顺时针填充。"""
    return tau * value / 100.0 - tau / 4


class Ring(Gtk.DrawingArea):
    def __init__(self, color: Gdk.RGBA, size: int = 44, stroke: int = 5):
        super().__init__()
        self._value = 0.0
        self._color = color
        self._stroke = stroke
        self._text = ""
        self._text_size = 12.0
        self.set_size_request(size, size)
        self.set_draw_func(self._draw)

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(100.0, value))
        self.queue_draw()

    def set_color(self, color: Gdk.RGBA) -> None:
        self._color = color
        self.queue_draw()

    def set_text(self, text: str) -> None:
        """中心文本（如 '33%'）；空串不绘制。"""
        self._text = text
        self.queue_draw()

    def set_text_size(self, size: float) -> None:
        self._text_size = size
        self.queue_draw()

    def _draw(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        r = (min(width, height) - self._stroke) / 2.0
        cx, cy = width / 2.0, height / 2.0
        base = (self._color.red, self._color.green, self._color.blue, self._color.alpha)

        # 底环
        cr.set_source_rgba(base[0], base[1], base[2], 0.15)
        cr.set_line_width(self._stroke)
        cr.arc(cx, cy, r, 0, tau)
        cr.stroke()

        # 分段渐变弧
        n = 32
        colors = ring_segment_colors(base, n)
        arc_end = ring_arc_end(self._value)
        for i in range(n):
            a0 = (tau * i / n) - tau / 4
            a1 = a0 + tau / n
            if a0 >= arc_end:
                break
            a1 = min(a1, arc_end)
            c = colors[i]
            cr.set_source_rgba(*c)
            cr.set_line_cap(1)  # CAIRO_LINE_CAP_ROUND
            cr.arc(cx, cy, r, a0, a1)
            cr.stroke()
            # 发光：同色低透明度稍粗描一遍
            cr.set_source_rgba(c[0], c[1], c[2], 0.35)
            cr.set_line_width(self._stroke + 1.0)
            cr.arc(cx, cy, r, a0, a1)
            cr.stroke()
            cr.set_line_width(self._stroke)

        # 中心文本（对齐原版：数值绘制在环形中心）
        if self._text:
            cr.select_font_face("Sans", 0, 1)  # CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD
            cr.set_font_size(self._text_size)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.92)
            x_bearing, y_bearing, tw, th, x_adv, y_adv = cr.text_extents(self._text)
            cr.move_to(cx - tw / 2 - x_bearing, cy - th / 2 - y_bearing)
            cr.show_text(self._text)
