"""GNOME Shell 定位扩展客户端。

扩展（linux/gnome-extension/org.sidebay.Positioner）在会话总线导出
org.sidebay.Positioner，经 MetaWindow.move_resize_frame 实现任意 X/Y 定位
（含 GNOME Wayland 下被合成器禁止的垂直移动）。

扩展不可用时所有方法返回 False/None，调用方回退到 X11 定位。
"""

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

EXTENSION_BUS_NAME = "org.sidebay.Positioner"
EXTENSION_OBJECT_PATH = "/org/sidebay/Positioner"
EXTENSION_IFACE = "org.sidebay.Positioner"


class PositionerClient:
    def __init__(self):
        self._proxy = None

    def _ensure(self) -> bool:
        if self._proxy is not None:
            return True
        try:
            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                EXTENSION_BUS_NAME,
                EXTENSION_OBJECT_PATH,
                EXTENSION_IFACE,
                None,
            )
            return True
        except GLib.Error:
            self._proxy = None
            return False

    def move_window(self, x: float, y: float, width: float, height: float) -> bool:
        """经扩展移动窗口；扩展不可用/调用失败返回 False（调用方回退 X11）。"""
        if not self._ensure():
            return False
        try:
            self._proxy.call_sync(
                "MoveWindow",
                GLib.Variant("(iiii)", (int(x), int(y), int(width), int(height))),
                Gio.DBusCallFlags.NONE,
                2000,
                None,
            )
            return True
        except GLib.Error:
            return False

    def window_info(self) -> tuple[int, int, int, int] | None:
        """返回 (x, y, width, height)；扩展不可用返回 None。"""
        if not self._ensure():
            return None
        try:
            res = self._proxy.call_sync(
                "GetWindowInfo", None, Gio.DBusCallFlags.NONE, 2000, None
            )
            return tuple(res.unpack()[0])
        except GLib.Error:
            return None
