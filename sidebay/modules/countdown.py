"""倒计时（番茄钟）：纯状态类 + GTK 视图。"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module


class CountdownState:
    def __init__(self, minutes: int = 25):
        self.minutes = minutes
        self.remaining = minutes * 60
        self.active = False

    def tick(self) -> bool:
        if not self.active or self.remaining <= 0:
            return False
        self.remaining -= 1
        if self.remaining == 0:
            self.active = False
            return True
        return False

    def set_minutes(self, m: int) -> None:
        if m > 0:
            self.remaining = m * 60
        self.active = False

    def reset(self) -> None:
        self.remaining = self.minutes * 60
        self.active = False

    def time_string(self) -> str:
        return f"{self.remaining // 60:02d}:{self.remaining % 60:02d}"


class CountdownModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self.state = CountdownState()
        self._lang = store.settings.language
        self._timer: int | None = None

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=t("Countdown", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        self._time_label = Gtk.Label(label=self.state.time_string())
        self._time_label.add_css_class("sb-tick-label")
        box.append(self._time_label)

        self._entry = Gtk.Entry()
        self._entry.set_visible(False)
        self._entry.connect("activate", self._on_submit)
        box.append(self._entry)

        gesture = Gtk.GestureClick(button=1)
        gesture.connect("pressed", lambda *_a: self._start_edit())
        self._time_label.add_controller(gesture)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._toggle_btn = Gtk.Button(label="▶")
        self._toggle_btn.add_css_class("sb-btn-glass")
        self._toggle_btn.connect("clicked", self._on_toggle)
        controls.append(self._toggle_btn)

        reset_btn = Gtk.Button(label="↺")
        reset_btn.add_css_class("sb-btn-glass")
        reset_btn.connect("clicked", self._on_reset)
        controls.append(reset_btn)
        box.append(controls)

        self._timer = GLib.timeout_add(1000, self._on_second)
        return self._boxed(box)

    def _start_edit(self) -> None:
        if self.state.active:
            return
        self._entry.set_text(str(self.state.minutes))
        self._entry.set_visible(True)
        self._time_label.set_visible(False)
        self._entry.grab_focus()

    def _on_submit(self, _entry) -> None:
        try:
            self.state.set_minutes(int(self._entry.get_text()))
        except ValueError:
            pass
        self._entry.set_visible(False)
        self._time_label.set_visible(True)
        self._time_label.set_text(self.state.time_string())

    def _on_toggle(self, _btn) -> None:
        self.state.active = not self.state.active
        self._toggle_btn.set_label("⏸" if self.state.active else "▶")

    def _on_reset(self, _btn) -> None:
        self.state.reset()
        self._toggle_btn.set_label("▶")
        self._time_label.set_text(self.state.time_string())

    def _on_second(self) -> bool:
        if self.state.tick():
            self._toggle_btn.set_label("▶")
        self._time_label.set_text(self.state.time_string())
        return True

    def on_destroy(self) -> None:
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
