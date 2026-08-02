"""CPU/GPU/Memory/Disk 环形仪表模块。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module
from sidebay.widgets.ring import Ring


class UsageModule(Module):
    KINDS = {"CPU": "cpu", "GPU": "gpu", "Memory": "memory", "Disk": "disk"}
    COLORS = {
        "CPU": (0.32, 0.60, 1.00),
        "GPU": (0.60, 0.45, 1.00),
        "Memory": (1.00, 0.65, 0.20),
        "Disk": (0.62, 0.48, 0.33),
    }

    def __init__(self, store, module_id, monitor, kind: str):
        super().__init__(store, module_id)
        self.monitor = monitor
        self.kind = kind
        self._ring: Ring | None = None
        self._lang = store.settings.language
        self._last_value: float | None = None

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label=t(self.kind, self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        rgba = Gdk.RGBA()
        rgba.parse(f"rgb({int(self.COLORS[self.kind][0]*255)}, {int(self.COLORS[self.kind][1]*255)}, {int(self.COLORS[self.kind][2]*255)})")
        self._ring = Ring(rgba, size=44, stroke=5)
        self._ring.set_text("0%")  # 百分比直接绘制在环形中心（对齐原版 UI）
        box.append(self._ring)
        return self._boxed(box)

    def on_tick(self) -> None:
        if self.monitor is None or self._ring is None:
            return
        value = getattr(self.monitor.last, self.KINDS[self.kind], 0.0)
        if self.kind == "Memory":
            last = self.monitor.last
            value = last.mem_used / last.mem_total * 100.0 if last.mem_total else 0.0
        elif self.kind == "Disk":
            value = self.monitor.last.disk_pct
        # 值未变时跳过更新（避免每 tick 触发重绘）
        if value == self._last_value:
            return
        self._last_value = value
        self._ring.set_value(value)
        self._ring.set_text(f"{value:.0f}%")
