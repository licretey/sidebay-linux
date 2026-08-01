"""无装饰、贴屏边缘、全高的主侧边栏窗口。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk

from sidebay.i18n import t
from sidebay.monitor import SystemMonitor

try:
    gi.require_version("GdkX11", "4.0")
except (ValueError, ImportError):
    pass  # 无 X11 环境时 _x11_dock 内导入失败静默跳过

EDGE_ZONE_WIDTH = 4
WIDTH_MIN = 40
WIDTH_MAX = 300


class SidebarWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store):
        super().__init__(application=app)
        self.store = store
        self.set_decorated(False)
        # GTK 4.22 移除了 gtk_window_set_keep_above；有该 API 时置顶，无则跳过
        if hasattr(self, "set_keep_above"):
            self.set_keep_above(True)
        self.set_resizable(False)
        self.set_title("Sidebay")

        self._module_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self._module_box)
        scroller.set_overlay_scrolling(True)

        self._opacity = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._opacity.set_range(0.1, 1.0)
        self._opacity.set_value(self.store.settings.opacity)
        self._opacity.set_hexpand(True)
        self._opacity.add_css_class("sb-slider")
        self._opacity.connect("value-changed", self._on_opacity_changed)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(scroller)
        outer.append(self._opacity)

        # 边缘拖拽改宽热区：叠在窗口根上，占 dock 对侧 ~4px 窄条
        overlay = Gtk.Overlay()
        overlay.set_child(outer)
        overlay.add_overlay(self._build_edge_zone())
        self.set_child(overlay)

        self._apply_position()
        self._apply_width()
        self._apply_opacity()
        self._monitor = SystemMonitor()
        self.rebuild_modules()

        self._tick_timer = GLib.timeout_add(1000, self._tick)
        self.connect("destroy", self._on_window_destroy)
        # realize 后 surface 才可用：此时再跑一次贴边逻辑（含 X11 XMoveResizeWindow）
        self.connect("realize", lambda *_: self._apply_width())
        self._build_context_menu()

    def _tick(self) -> bool:
        self._monitor.last = self._monitor.tick()
        for module in getattr(self, "_modules", []):
            try:
                module.on_tick()
            except Exception:
                pass
        return True

    def _on_window_destroy(self, *_a) -> None:
        GLib.source_remove(self._tick_timer)

    def rebuild_modules(self) -> None:
        from sidebay.modules.registry import create_module

        # remove 先解除父子引用，run_dispose 再触发 destroy 信号 → module.on_destroy → 定时器清理
        while (child := self._module_box.get_first_child()) is not None:
            self._module_box.remove(child)
            child.run_dispose()
        self._modules: list = []
        for m in self.store.modules:
            if m.type not in ("CPU", "GPU", "Memory", "Disk", "Fan", "Network", "Calculator", "Stock",
                              "Countdown", "Stopwatch", "Keyboard"):
                continue  # Task 8-11 逐步放开
            try:
                module = create_module(m.type, self.store, m.module_id, self._monitor)
            except ValueError:
                continue
            widget = module.build()
            # 模块高度：height_pct > 0 时按侧边栏高度百分比，否则用 base._boxed 的 100px 默认
            if m.height_pct and m.height_pct > 0:
                window_height = self._workarea[3] if hasattr(self, "_workarea") else 100
                widget.set_size_request(-1, int(m.height_pct / 100 * window_height))
            self._modules.append(module)
            self._module_box.append(widget)

    def _on_opacity_changed(self, scale: Gtk.Scale) -> None:
        value = scale.get_value()
        self.set_opacity(value)
        self.store.settings.opacity = value
        self.store.save()

    def _apply_position(self) -> None:
        display = self.get_display()
        monitors = display.get_monitors()
        if monitors.get_n_items() == 0:
            return
        native = self.get_native()
        surface = native.get_surface() if native is not None else None
        monitor = (display.get_monitor_at_surface(surface)
                   if surface is not None else monitors.get_item(0))
        if monitor is None:
            return
        # GTK 4.22：Gdk.Monitor.get_workarea 已移除，用 get_geometry 代替
        geom = monitor.get_geometry()
        self._workarea = (geom.x, geom.y, geom.width, geom.height)

    def _apply_width(self) -> None:
        if not hasattr(self, "_workarea"):
            return
        _, y, w, h = self._workarea
        width = int(self.store.settings.width) if self.store.settings.width > 0 else int(w / 20)
        self.set_default_size(width, h)
        # GTK 4.22 移除了 gtk_window_resize/gtk_window_move；有该 API 时再调用
        if hasattr(self, "resize"):
            self.resize(width, h)
        if hasattr(self, "move"):
            self.move(
                self._workarea[0] if self.store.settings.position == "left"
                else self._workarea[0] + self._workarea[2] - width,
                y,
            )
        self._x11_dock(width, h)

    def _x11_dock(self, width: int, height: int) -> None:
        """X11 后端：XMoveResizeWindow 直接贴边定位/改宽（失败静默，绝不崩溃）。

        Wayland（无 X11Surface）下跳过：窗口停留在 GTK 放置的位置。
        """
        try:
            from gi.repository import GdkX11
        except Exception:
            return
        try:
            import ctypes

            native = self.get_native()
            surface = native.get_surface() if native is not None else None
            if surface is None or not isinstance(surface, GdkX11.X11Surface):
                return
            xid = surface.get_xid()
            if not xid:  # 未 realize 时无有效 XID（本 GTK 的 typelib 不暴露 is_realized）
                return
            lib = ctypes.CDLL("libX11.so.6")
            lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            lib.XMoveResizeWindow.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong,
                ctypes.c_int, ctypes.c_int,
                ctypes.c_uint, ctypes.c_uint,
            ]
            lib.XMoveResizeWindow.restype = ctypes.c_int
            lib.XFlush.argtypes = [ctypes.c_void_p]
            lib.XFlush.restype = ctypes.c_int
            lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            lib.XCloseDisplay.restype = ctypes.c_int
            display = lib.XOpenDisplay(None)
            if not display:
                return
            x = (self._workarea[0] if self.store.settings.position == "left"
                 else self._workarea[0] + self._workarea[2] - width)
            lib.XMoveResizeWindow(display, xid, x, self._workarea[1], width, height)
            lib.XFlush(display)
            lib.XCloseDisplay(display)
        except Exception:
            pass

    def _apply_opacity(self) -> None:
        self.set_opacity(self.store.settings.opacity)

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

    def _current_width(self) -> float:
        width = self.store.settings.width
        if width > 0:
            return width
        if hasattr(self, "_workarea") and self._workarea[2] > 0:
            return self._workarea[2] / 20
        return 100.0

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
