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
            import threading

            if "DISPLAY" not in os.environ:
                return None
            from Xlib import X, display as xdisplay
            from Xlib.ext import record
            from Xlib.protocol import rq

            self._xdisplay = xdisplay.Display()

            def on_reply(reply):
                try:
                    if reply.category != record.FromServer or reply.client_swapped:
                        return
                    data = reply.data
                    while len(data) >= 32:
                        event, data = rq.EventField(None).parse_binary_value(
                            data, self._xdisplay.display, None, None
                        )
                        if event.type == X.KeyPress:  # 键按下且过滤掉 modifier-only 事件
                            mods = set()
                            if event.state & 0x0004:
                                mods.add("Control")
                            if event.state & 0x0008:
                                mods.add("Alt")
                            if event.state & 0x0001:
                                mods.add("Shift")
                            if event.state & 0x0040:
                                mods.add("Super")
                            keysym = self._xdisplay.keycode_to_keysym(event.detail, 0)
                            symbol = self._keysym_to_str(keysym) if keysym else None
                            text = format_keys(mods, symbol)
                            if text:
                                GLib.idle_add(self._show, text)
                except Exception:
                    pass  # 监听回调永不抛错

            self._xrecord_ctx = self._xdisplay.record_create_context(
                0,
                [record.AllClients],
                [{
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0, 0, 0),
                    "ext_replies": (0, 0, 0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (X.KeyPress, X.ButtonRelease),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }],
            )
            # record_enable_context 阻塞到 EndOfData（disable/free 前不会返回），
            # 必须在后台线程运行；回调在线程内同步触发，经 GLib.idle_add 切回主循环
            self._record_thread = threading.Thread(
                target=self._xdisplay.record_enable_context,
                args=(self._xrecord_ctx, on_reply),
                daemon=True,
            )
            self._record_thread.start()
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
                self._xdisplay.record_disable_context(self._xrecord_ctx)
                self._xdisplay.flush()  # 让记录线程尽快收到 EndOfData 并退出
                self._xdisplay.record_free_context(self._xrecord_ctx)
        except Exception:
            pass
