"""网络上下行速率模块。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module


def format_bytes(bytes_per_sec: float) -> str:
    if bytes_per_sec > 1_048_576:
        return f"{bytes_per_sec / 1_048_576:.1f} MB/s"
    if bytes_per_sec > 1024:
        return f"{bytes_per_sec / 1024:.0f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"


# 上下行箭头色（规格：绿↑蓝↓）
UP_COLOR = (0.20, 0.85, 0.40)
DOWN_COLOR = (0.32, 0.60, 1.00)


def arrow_markup(arrow: str, text: str, color: tuple) -> str:
    """生成带颜色的箭头 markup；纯函数便于单测。"""
    r, g, b = (round(c * 255) for c in color)
    return f'<span foreground="#{r:02X}{g:02X}{b:02X}">{arrow}</span>  {text}'


class NetworkModule(Module):
    def __init__(self, store, module_id, monitor):
        super().__init__(store, module_id)
        self.monitor = monitor
        self._up: Gtk.Label | None = None
        self._down: Gtk.Label | None = None
        self._lang = store.settings.language

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._title(t("Network", self._lang)))
        self._up = self._row("▲", UP_COLOR, "sb-tick-label")
        self._down = self._row("▼", DOWN_COLOR, "sb-tick-label")
        box.append(self._up)
        box.append(self._down)
        return self._boxed(box)

    def _title(self, text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.add_css_class("sb-module-title")
        return label

    def _row(self, arrow: str, color: tuple, css: str) -> Gtk.Label:
        label = Gtk.Label()
        label.add_css_class(css)
        label.set_halign(Gtk.Align.CENTER)
        self._render(label, arrow, "0 B/s", color)
        return label

    @staticmethod
    def _render(label: Gtk.Label, arrow: str, text: str, color: tuple) -> None:
        """箭头按 color 着色，速率文本保持 format_bytes 输出。"""
        label.set_markup(arrow_markup(arrow, text, color))

    def on_tick(self) -> None:
        if self.monitor is None or self._up is None:
            return
        self._render(self._up, "▲", format_bytes(self.monitor.last.net_up), UP_COLOR)
        self._render(self._down, "▼", format_bytes(self.monitor.last.net_down), DOWN_COLOR)
