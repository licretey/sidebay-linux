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
        # 必须 vexpand：否则 GTK4 ScrolledWindow 只取 min-content-height（默认 46px），
        # 视口裁剪掉第一个模块以下的所有内容
        scroller.set_vexpand(True)

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
        # 深色玻璃质感背景（与设置窗口一致；缺此窗口全透明）
        overlay.add_css_class("sb-glass")
        self._font_overlay = overlay
        self._font_provider: Gtk.CssProvider | None = None
        self._positioner = None  # 惰性初始化：GNOME 定位扩展客户端
        self._apply_font_css()
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
        # map 后合成器（Mutter）的初始放置会持续约数秒，期间移动会被覆盖：
        # 在 500ms/2s/5s 各重试一次定位，确保最终位置（贴边或手动坐标）落位
        self.connect("map", self._schedule_redock)
        self._build_context_menu()
        self._build_long_press()

    def _schedule_redock(self, *_a) -> None:
        for delay in (500, 2000, 5000):
            GLib.timeout_add(delay, self._redock_once)

    def _redock_once(self) -> bool:
        self._apply_width()
        return False

    # ---------- 手动定位 ----------

    def apply_position_xy(self, x: float, y: float) -> None:
        """设置页实时定位：优先 GNOME 扩展（任意 X/Y，含 Wayland 垂直移动）；
        扩展不可用时回退 X11（Wayland 下仅 X 有效）。"""
        height = self.get_height() if self.get_height() > 0 else (
            self._workarea[3] if hasattr(self, "_workarea") else 800
        )
        if self._positioner_move(x, y, height):
            return
        self._x11_dock(int(self._current_width()), height, x=int(x), y=int(y))

    def _positioner_move(self, x: float, y: float, height: float) -> bool:
        try:
            from sidebay.positioner import PositionerClient

            if self._positioner is None:
                self._positioner = PositionerClient()
            return self._positioner.move_window(
                x, y, int(self._current_width()), height
            )
        except Exception:
            return False

    def apply_font_style(self) -> None:
        """设置页字号/字体变更后即时重应用（侧边栏与设置窗口均调用）。"""
        self._apply_font_css()

    def _apply_font_css(self) -> None:
        overlay = self._font_overlay
        for cls in ("sb-font-small", "sb-font-large"):
            overlay.remove_css_class(cls)
        size = self.store.settings.font_size or "medium"
        if size != "medium":
            overlay.add_css_class(f"sb-font-{size}")
        if self._font_provider is not None:
            self.get_style_context().remove_provider(self._font_provider)
            self._font_provider = None
        family = self.store.settings.font_family
        if family:
            # 字体族是继承属性：窗口级提供器 `*` 规则级联到所有子控件
            # （sb-tick-label 等显式 font-family: monospace 的除外）
            self._font_provider = Gtk.CssProvider()
            self._font_provider.load_from_string(f"* {{ font-family: '{family}'; }}")
            self.get_style_context().add_provider(self._font_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

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
                work_h = self._workarea[3] if hasattr(self, "_workarea") else 100
                window_height = self.store.settings.height or work_h
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
        if self.store.settings.height is not None:
            h = int(self.store.settings.height)  # 手动高度：内容滚动
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
        if self.store.settings.pos_x is not None and self.store.settings.pos_y is not None:
            # 手动定位优先：直接放置到用户设定的坐标（扩展优先，回退 X11）
            if not self._positioner_move(self.store.settings.pos_x, self.store.settings.pos_y, h):
                self._x11_dock(width, h, x=int(self.store.settings.pos_x), y=int(self.store.settings.pos_y))
        else:
            self._x11_dock(width, h)

    def _x11_dock(self, width: int, height: int, x: int | None = None, y: int | None = None) -> None:
        """X11 后端：XMoveResizeWindow 定位/改宽（失败静默，绝不崩溃）。

        x/y 缺省时按贴边逻辑计算（position 设置）；显式传入时用传入坐标（手动定位）。
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
            if x is None:
                x = (self._workarea[0] if self.store.settings.position == "left"
                     else self._workarea[0] + self._workarea[2] - width)
            if y is None:
                y = self._workarea[1]
            lib.XMoveResizeWindow(display, xid, x, y, width, height)
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
