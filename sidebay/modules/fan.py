"""风扇模块：旋转扇叶 + RPM。扇叶 6 片，转速 rpm*0.18 度/秒（对齐原版）。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module

from math import cos, pi, sin


class FanModule(Module):
    def __init__(self, store, module_id, monitor):
        super().__init__(store, module_id)
        self.monitor = monitor
        self._angle = 0.0
        self._timer: int | None = None
        self._rpm_label: Gtk.Label | None = None
        self._lang = store.settings.language

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label=t("Fan", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        area = Gtk.DrawingArea()
        area.set_size_request(44, 44)
        area.set_draw_func(self._draw_blades)
        box.append(area)

        self._rpm_label = Gtk.Label(label="0 RPM")
        self._rpm_label.add_css_class("sb-tick-label")
        box.append(self._rpm_label)

        self._timer = GLib.timeout_add(100, self._advance)
        return self._boxed(box)

    def _advance(self) -> bool:
        # 30ms 定时器可能先于首次 1s tick 触发，monitor.last 尚未赋值——需容忍
        last = getattr(self.monitor, "last", None) if self.monitor is not None else None
        rpm = last.fan_rpm if last is not None else 0
        self._angle = (self._angle + rpm * 0.18 * 0.03) % 360.0
        if self._rpm_label is not None:
            self._rpm_label.set_text(f"{rpm} RPM")
        self._redraw()
        return True

    def _redraw(self) -> None:
        parent = self._rpm_label.get_parent()
        if parent is not None:
            area = parent.get_first_child().get_next_sibling()
            if isinstance(area, Gtk.DrawingArea):
                area.queue_draw()

    def _draw_blades(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        cx, cy, r = width / 2, height / 2, min(width, height) / 2 - 4
        cr.translate(cx, cy)
        cr.rotate(self._angle * pi / 180.0)
        for i in range(6):
            cr.save()
            cr.rotate(i * 2 * pi / 6)
            cr.scale(1.0, 0.42)  # 椭圆扇叶
            cr.set_source_rgba(0.2, 0.8, 0.8, 0.9)
            cr.arc(0, -r * 0.55, r * 0.38, 0, 2 * pi)
            cr.fill()
            cr.restore()
        cr.set_source_rgba(0.2, 0.8, 0.8, 0.25)
        cr.arc(0, 0, 3, 0, 2 * pi)
        cr.fill()

    def on_destroy(self) -> None:
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
