"""窗口定位与 X11 窗口类型：PositioningMixin（SidebarWindow 组合使用）。"""

import ctypes

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk


class PositioningMixin:
    def _schedule_redock(self, *_a) -> None:
        for delay in (500, 2000, 5000):
            GLib.timeout_add(delay, self._redock_once)

    def _redock_once(self) -> bool:
        self._apply_width()
        return False

    # ---------- 手动定位 ----------

    def apply_position_xy(self, x: float, y: float) -> None:
        """设置页实时定位：XWayland/X11 下 XMoveResizeWindow 移动窗口（含 Y）。

        注意：Mutter 初始放置窗口期（启动后数秒）移动会被覆盖，且全高窗口
        下移会因超出屏幕被钳回顶部——配合「高度」控件使用短窗口即可任意定位。
        """
        height = self.get_height() if self.get_height() > 0 else (
            self._workarea[3] if hasattr(self, "_workarea") else 800
        )
        self._x11_dock(int(self._current_width()), height, x=int(x), y=int(y))

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
            # 手动定位优先：直接放置到用户设定的坐标
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

    def _set_x11_window_type(self) -> None:
        """把窗口标记为 DOCK 类型（_NET_WM_WINDOW_TYPE_DOCK + SKIP_TASKBAR）：
        窗口可见但不出现在 Dock/任务栏/Alt-Tab（GNOME 对 dock 类型窗口的
        标准处理，Plank 等停靠栏同款）。仅 X11/XWayland 下生效，失败静默。
        """
        try:
            from gi.repository import GdkX11

            native = self.get_native()
            surface = native.get_surface() if native is not None else None
            if surface is None or not isinstance(surface, GdkX11.X11Surface):
                return
            xid = surface.get_xid()
            if not xid:
                return
            lib = ctypes.CDLL("libX11.so.6")
            lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            lib.XInternAtom.restype = ctypes.c_ulong
            lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            lib.XChangeProperty.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
                ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
            ]
            lib.XFlush.argtypes = [ctypes.c_void_p]
            lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            display = lib.XOpenDisplay(None)
            if not display:
                return
            XA_ATOM = 4  # 预定义原子
            # _NET_WM_WINDOW_TYPE = DOCK
            prop = lib.XInternAtom(display, b"_NET_WM_WINDOW_TYPE", False)
            value = lib.XInternAtom(display, b"_NET_WM_WINDOW_TYPE_DOCK", False)
            arr = (ctypes.c_ulong * 1)(value)
            lib.XChangeProperty(display, xid, prop, XA_ATOM, 32, 0, arr, 1)
            # _NET_WM_STATE += SKIP_TASKBAR
            prop2 = lib.XInternAtom(display, b"_NET_WM_STATE", False)
            value2 = lib.XInternAtom(display, b"_NET_WM_STATE_SKIP_TASKBAR", False)
            arr2 = (ctypes.c_ulong * 1)(value2)
            lib.XChangeProperty(display, xid, prop2, XA_ATOM, 32, 0, arr2, 1)
            lib.XFlush(display)
            lib.XCloseDisplay(display)
        except Exception:
            pass

    def _current_width(self) -> float:
        width = self.store.settings.width
        if width > 0:
            return width
        if hasattr(self, "_workarea") and self._workarea[2] > 0:
            return self._workarea[2] / 20
        return 100.0
