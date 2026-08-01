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

            self._xdisplay = xdisplay.Display()

            self._record = record  # 供 _on_record_reply 使用

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
                target=self._record_loop,
                daemon=True,
            )
            self._record_thread.start()
            return True
        except Exception:
            return None

    def _record_loop(self) -> None:
        """记录线程主体：异常全部吞掉，绝不让线程带未捕获异常退出。

        on_destroy 关闭连接会从 recv 侧抛出连接错误/TypeError，这正是
        「正常停止」的路径；不包住的话线程异常会在退出阶段浮出水面。
        """
        try:
            self._xdisplay.record_enable_context(self._xrecord_ctx, self._on_record_reply)
        except Exception:
            pass

    def _on_record_reply(self, reply) -> None:
        try:
            from Xlib import X
            from Xlib.protocol import rq

            if reply.category != self._record.FromServer or reply.client_swapped:
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
        """完整回收：disable → join 记录线程 → free context → close display。

        全程异常防护：任何一步失败都不影响应用退出，且不留下泄漏或崩溃窗口。
        python-xlib 的线程化 recv 协调器在部分环境（如 Xvfb）不响应跨线程
        disable，线程会一直阻塞在 select——而 close() 关闭 fd 也不会唤醒阻塞的
        select。此时用 socket.shutdown() 使 fd 变为可读/HUP，线程在 recv 侧
        抛出 ConnectionClosedError，已被 _record_loop 吞掉并干净退出。
        """
        thread = getattr(self, "_record_thread", None)
        if self._listener is None or thread is None:
            return
        try:
            self._xdisplay.record_disable_context(self._xrecord_ctx)
            self._xdisplay.flush()  # 让记录线程尽快收到 EndOfData 并退出
            thread.join(timeout=1.0)
        except Exception:
            pass
        if not thread.is_alive():
            try:
                self._xdisplay.record_free_context(self._xrecord_ctx)
                self._xdisplay.close()
            except Exception:
                pass
            return
        try:
            self._xdisplay.display.socket.shutdown(2)  # SHUT_RDWR：唤醒阻塞的 select
        except Exception:
            pass
        try:
            thread.join(timeout=1.0)
        except Exception:
            pass
        if thread.is_alive():
            return  # 极端情况：守护线程随进程退出，不做危险操作
        try:
            self._xdisplay.record_free_context(self._xrecord_ctx)
            self._xdisplay.close()
        except Exception:
            pass
