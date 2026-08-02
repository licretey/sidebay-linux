"""Gtk.Application：单实例、CSS 装载、窗口管理。"""

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gio, Gtk

from sidebay.store import Store
from sidebay.window import SidebarWindow

CSS_PATH = Path(__file__).parent / "style.css"


def autostart_exec_line() -> str:
    """计算写入 ~/.config/autostart/sidebay.desktop 的 Exec 行。

    Flatpak 沙盒内（FLATPAK_ID 由运行时注入）宿主 python3 无 sidebay 模块，
    必须用 `flatpak run` 启动；直接运行则用仓库 run.sh 的绝对路径。
    """
    if os.environ.get("FLATPAK_ID"):
        return "flatpak run org.sidebay.SideBay"
    return str(Path(__file__).resolve().parent.parent / "run.sh")


class SidebayApplication(Gtk.Application):
    def __init__(self, store: Store | None = None, **kwargs):
        super().__init__(application_id="org.sidebay.SideBay", **kwargs)
        self.store = store or Store()
        self.window: SidebarWindow | None = None
        self.settings_window = None
        self.connect("startup", self._on_startup)

    def _on_startup(self, app) -> None:
        # 强制深色主题偏好：Flatpak 沙盒内取不到宿主主题，默认 Adwaita 亮色，
        # 未自绘样式的控件（输入框/下拉/开关）会变成乳白色
        try:
            settings = Gtk.Settings.get_default()
            for prop, value in (("gtk-application-prefer-dark-theme", True),
                                ("gtk-color-scheme", "prefer-dark")):
                try:
                    settings.set_property(prop, value)
                except Exception:
                    pass
        except Exception:
            pass
        provider = Gtk.CssProvider()
        provider.load_from_path(str(CSS_PATH))
        # GTK 4.22：Gtk.Window.get_default_display 已移除，用 Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return
        # 后台运行：应用 hold 保活，窗口全部隐藏后不退出
        self.hold()
        # 延迟到主循环空闲时注册托盘：do_activate 早于主循环启动，
        # 立即注册时 watcher 异步探测我们的对象无法分发回调，会被丢弃
        GLib.idle_add(self._start_tray_deferred)

    def _start_tray_deferred(self) -> bool:
        try:
            from sidebay.tray import TrayIcon

            tray = TrayIcon(self)
            if tray.start():
                self.tray = tray
                return False
        except Exception:
            pass
        # 无托盘（无 AppIndicator 扩展等）：回退为直接显示窗口
        self.tray = None
        self.create_window()
        return False

    def _on_open_settings(self, *_a) -> None:
        from sidebay.settings import SettingsWindow

        if self.settings_window is not None:
            self.settings_window.present()
            return
        self.settings_window = SettingsWindow(
            self, self.store,
            exec_line=autostart_exec_line(),
            on_close_callback=lambda: (
                self.window.rebuild_modules() if self.window else None,
                self.window._apply_width() if self.window else None,
                self.window._apply_position() if self.window else None,
                setattr(self, "settings_window", None),
            ),
            on_position_change=(
                (lambda x, y: self.window.apply_position_xy(x, y)) if self.window else None
            ),
            on_style_change=(
                (lambda: (self.window.apply_font_style(), self.window._apply_opacity(),
                          self.window._apply_width()))
                if self.window else None
            ),
        )
        self.settings_window.present()

    def create_window(self) -> SidebarWindow:
        self.window = SidebarWindow(self, self.store)
        self.window.present()
        self._register_settings_action()
        return self.window

    def _register_settings_action(self) -> None:
        action = Gio.SimpleAction.new("open-settings", None)
        action.connect("activate", self._on_open_settings)
        self.add_action(action)
