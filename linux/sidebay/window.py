"""无装饰、贴屏边缘、全高的主侧边栏窗口。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk

from sidebay.monitor import SystemMonitor


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
        self.set_child(outer)

        self._apply_position()
        self._apply_width()
        self._apply_opacity()
        self._monitor = SystemMonitor()
        self.rebuild_modules()

        self._tick_timer = GLib.timeout_add(1000, self._tick)
        self.connect("destroy", self._on_window_destroy)

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

        while (child := self._module_box.get_first_child()) is not None:
            self._module_box.remove(child)
        self._modules: list[Module] = []
        for m in self.store.modules:
            if m.type not in ("CPU", "GPU", "Memory", "Disk", "Fan", "Network", "Calculator", "Stock"):
                continue  # Task 8-11 逐步放开
            try:
                module = create_module(m.type, self.store, m.module_id, self._monitor)
            except ValueError:
                continue
            self._modules.append(module)
            self._module_box.append(module.build())

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

    def _apply_opacity(self) -> None:
        self.set_opacity(self.store.settings.opacity)
