"""秒表：纯状态类 + GTK 视图。"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module


class StopwatchState:
    def __init__(self):
        self.elapsed = 0
        self.active = False

    def tick(self) -> None:
        if self.active:
            self.elapsed += 1

    def toggle(self) -> None:
        self.active = not self.active

    def reset(self) -> None:
        self.active = False
        self.elapsed = 0

    def time_string(self) -> str:
        return f"{self.elapsed // 60:02d}:{self.elapsed % 60:02d}"


class StopwatchModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self.state = StopwatchState()
        self._lang = store.settings.language

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=t("Stopwatch", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        self._time_label = Gtk.Label(label="00:00")
        self._time_label.add_css_class("sb-tick-label")
        box.append(self._time_label)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._toggle_btn = Gtk.Button(label="▶")
        self._toggle_btn.add_css_class("sb-btn-glass")
        self._toggle_btn.connect("clicked", self._on_toggle)
        controls.append(self._toggle_btn)

        stop_btn = Gtk.Button(label="⏹")
        stop_btn.add_css_class("sb-btn-glass")
        stop_btn.connect("clicked", self._on_stop)
        controls.append(stop_btn)
        box.append(controls)

        return self._boxed(box)

    def _on_toggle(self, _btn) -> None:
        self.state.toggle()
        self._toggle_btn.set_label("⏸" if self.state.active else "▶")

    def _on_stop(self, _btn) -> None:
        self.state.reset()
        self._toggle_btn.set_label("▶")
        self._time_label.set_text("00:00")

    def on_tick(self) -> None:
        # 窗口 tick 每秒驱动（refresh_interval 强制 1s）
        self.state.tick()
        self._time_label.set_text(self.state.time_string())
