"""Gtk.Application：单实例、CSS 装载、窗口管理。"""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, Gtk

from sidebay.store import Store
from sidebay.window import SidebarWindow

CSS_PATH = Path(__file__).parent / "style.css"


class SidebayApplication(Gtk.Application):
    def __init__(self, store: Store | None = None, **kwargs):
        super().__init__(application_id="org.sidebay.SideBay", **kwargs)
        self.store = store or Store()
        self.window: SidebarWindow | None = None
        self.settings_window = None
        self.connect("startup", self._on_startup)

    def _on_startup(self, app) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_path(str(CSS_PATH))
        # GTK 4.22：Gtk.Window.get_default_display 已移除，用 Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def do_activate(self) -> None:
        if self.window is None:
            self.create_window()
        else:
            self.window.present()

    def _on_open_settings(self, *_a) -> None:
        from sidebay.settings import SettingsWindow

        if self.settings_window is not None:
            self.settings_window.present()
            return
        self.settings_window = SettingsWindow(
            self, self.store,
            exec_line="python3 -m sidebay",
            on_close_callback=lambda: (
                self.window.rebuild_modules() if self.window else None,
                setattr(self, "settings_window", None),
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
