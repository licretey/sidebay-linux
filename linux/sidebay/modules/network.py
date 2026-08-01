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
        self._up = self._row("▲", (0.20, 0.85, 0.40), "sb-tick-label")
        self._down = self._row("▼", (0.32, 0.60, 1.00), "sb-tick-label")
        box.append(self._up)
        box.append(self._down)
        return self._boxed(box)

    def _title(self, text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.add_css_class("sb-module-title")
        return label

    def _row(self, arrow: str, color: tuple, css: str) -> Gtk.Label:
        label = Gtk.Label(label=f"{arrow}  0 B/s")
        label.add_css_class(css)
        label.set_halign(Gtk.Align.CENTER)
        return label

    def on_tick(self) -> None:
        if self.monitor is None or self._up is None:
            return
        self._up.set_text(f"▲  {format_bytes(self.monitor.last.net_up)}")
        self._down.set_text(f"▼  {format_bytes(self.monitor.last.net_down)}")
