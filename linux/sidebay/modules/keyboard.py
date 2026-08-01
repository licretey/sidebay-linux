"""全局键盘监视：X11 XRecord 监听（best-effort）；Wayland/无 X 显示「无权限」。"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module

_MOD_ORDER = [("Control", "⌃"), ("Alt", "⌥"), ("Shift", "⇧"), ("Super", "⌘")]


def format_keys(mods: set[str], symbol: str | None) -> str:
    parts = [glyph for name, glyph in _MOD_ORDER if name in mods]
    if symbol:
        parts.append(symbol)
    return " ".join(parts)


class KeyboardModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self._lang = store.settings.language
        self._label: Gtk.Label | None = None
        self._listener = None

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        title = Gtk.Label(label=t("KEYS", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        self._label = Gtk.Label(label=" ")
        self._label.add_css_class("sb-tick-label")
        box.append(self._label)

        self._listener = self._try_start_listener()
        if self._listener is None:
            self._label.set_text(t("No Accessibility", self._lang))
        return self._boxed(box)

    def _try_start_listener(self):
        """连接 XRecord；任何失败都返回 None（应用不受影响）。"""
        try:
            import os

            if "DISPLAY" not in os.environ:
                return None
            from Xlib import display as xdisplay
            from Xlib import protocol
            from Xlib.Xrecord import Xrecord

            self._xdisplay = xdisplay.Display()

            def on_keys(event):
                try:
                    data = event.data
                    detail = data.detail
                    state = data.state
                    # 键按下且过滤掉 modifier-only 事件
                    if data.type == 2:  # KeyPress
                        mods = set()
                        if state & 0x0004:
                            mods.add("Control")
                        if state & 0x0008:
                            mods.add("Alt")
                        if state & 0x0001:
                            mods.add("Shift")
                        if state & 0x0040:
                            mods.add("Super")
                        keysym = self._xdisplay.keycode_to_keysym(detail, 0)
                        symbol = self._keysym_to_str(keysym) if keysym else None
                        text = format_keys(mods, symbol)
                        if text:
                            GLib.idle_add(self._show, text)
                except Exception:
                    pass  # 监听回调永不抛错

            self._xrecord_ctx = Xrecord(self._xdisplay)
            ranges = [{
                "first": 8,
                "last": 255,
                "core_requests": 0,
                "core_replies": 0,
                "ext_requests": 0,
                "ext_replies": 0,
                "delivered_events": 0,
                "device_events": 1 << 0,  # KeyPress
                "errors": 0,
                "client_started": 0,
                "client_done": 0,
            }]
            self._xrecord_ctx.start_context(on_keys, ranges)
            return True
        except Exception:
            return None

    def _keysym_to_str(self, keysym: int) -> str:
        try:
            from Xlib import XK

            name = XK.keysym_to_string(keysym)
            if not name:
                return None
            if len(name) == 1 and name.isprintable():
                return name.upper() if name.isalpha() else name
            return name
        except Exception:
            return None

    def _show(self, text: str) -> None:
        if self._label is not None:
            self._label.set_text(text)
            GLib.timeout_add(1500, self._clear, text)

    def _clear(self, text: str) -> bool:
        if self._label is not None and self._label.get_text() == text:
            self._label.set_text(" ")
        return False

    def on_destroy(self) -> None:
        try:
            if self._listener is not None and hasattr(self, "_xrecord_ctx"):
                self._xrecord_ctx.stop_context()
        except Exception:
            pass
