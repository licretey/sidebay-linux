"""窗口手势：长按打开设置、右键菜单、边缘拖拽改宽（GesturesMixin）。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk

from sidebay.i18n import t

EDGE_ZONE_WIDTH = 4
WIDTH_MIN = 40
WIDTH_MAX = 300


class GesturesMixin:
    # ---------- 边缘拖拽改宽热区 ----------

    def _build_edge_zone(self) -> Gtk.Widget:
        zone = Gtk.Box()
        zone.set_size_request(EDGE_ZONE_WIDTH, -1)
        zone.set_vexpand(True)
        zone.set_cursor_from_name("ew-resize")
        zone.add_css_class("sb-edge-zone")
        # 热区在 dock 位置对侧：dock 左边 → 右边缘可拖；dock 右边 → 左边缘可拖
        if self.store.settings.position == "left":
            zone.set_halign(Gtk.Align.END)
        else:
            zone.set_halign(Gtk.Align.START)
        gesture = Gtk.GestureDrag()
        gesture.connect("drag-begin", self._on_edge_drag_begin)
        gesture.connect("drag-update", self._on_edge_drag_update)
        gesture.connect("drag-end", self._on_edge_drag_end)
        zone.add_controller(gesture)
        return zone

    def _on_edge_drag_begin(self, gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
        self._drag_start_width = int(self._current_width())

    def _on_edge_drag_update(self, gesture: Gtk.GestureDrag, offset_x: float, _offset_y: float) -> None:
        # 右边缘向外拖为正增宽；左边缘反之
        delta = offset_x if self.store.settings.position == "left" else -offset_x
        new_width = max(WIDTH_MIN, min(WIDTH_MAX, int(self._drag_start_width + delta)))
        if new_width == self.store.settings.width:
            return
        self.store.settings.width = float(new_width)
        self._apply_width()

    def _on_edge_drag_end(self, gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
        self.store.save()

    # ---------- 长按打开设置 ----------

    def _build_long_press(self) -> None:
        self._long_press_timer: int | None = None
        gesture = Gtk.GestureClick(button=1)
        gesture.connect("pressed", self._on_press_start)
        gesture.connect("released", self._on_press_end)
        gesture.connect("cancel", self._on_press_end)
        # 注意：不监听 "stopped" —— GTK4 GestureClick 内置长按检测，
        # 按住约 500ms 会提前发 stopped 结束本次点击，会误取消 1.5s 定时器
        self.add_controller(gesture)

    def _on_press_start(self, _gesture, _n, _x, _y) -> None:
        self._cancel_long_press()
        self._long_press_timer = GLib.timeout_add(1500, self._on_long_press)

    def _on_press_end(self, *_a) -> None:
        self._cancel_long_press()

    def _cancel_long_press(self) -> None:
        if self._long_press_timer is not None:
            GLib.source_remove(self._long_press_timer)
            self._long_press_timer = None

    def _on_long_press(self) -> bool:
        self._long_press_timer = None
        self.activate_action("app.open-settings", None)
        return False

    # ---------- 右键菜单 ----------

    def _build_context_menu(self) -> None:
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self._on_right_click)
        self.add_controller(gesture)

    def _on_right_click(self, _gesture, _n, _x, _y) -> None:
        menu = Gtk.PopoverMenu()
        settings_btn = Gtk.Button(label=t("SettingsTitle", self.store.settings.language))
        settings_btn.connect("clicked", lambda *_: (menu.popdown(), self.activate_action("app.open-settings", None)))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(settings_btn)
        menu.set_child(box)
        menu.set_parent(self)
        menu.popup_at_pointer(None)  # 在当前指针位置弹出
