"""无装饰、贴屏边缘、全高的主侧边栏窗口。"""

import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk

from sidebay.i18n import t
from sidebay.monitor import SystemMonitor
from sidebay.gestures import GesturesMixin
from sidebay.positioning import PositioningMixin

try:
    gi.require_version("GdkX11", "4.0")
except (ValueError, ImportError):
    pass  # 无 X11 环境时 _x11_dock 内导入失败静默跳过



class SidebarWindow(Gtk.ApplicationWindow, PositioningMixin, GesturesMixin):
    def __init__(self, app, store):
        super().__init__(application=app)
        self.store = store
        self.set_decorated(False)
        # GTK 4.22 移除了 gtk_window_set_keep_above；有该 API 时置顶，无则跳过
        if hasattr(self, "set_keep_above"):
            self.set_keep_above(True)
        self.set_resizable(False)
        self.set_title("Sidebay")
        # 窗口图标：匹配 flatpak 安装的图标名（org.sidebay.SideBay）；直跑无主题图标时忽略
        if hasattr(self, "set_icon_name"):
            self.set_icon_name("org.sidebay.SideBay")

        self._module_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._module_box.set_margin_top(15)  # 第一个监控项顶部留白
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self._module_box)
        scroller.set_overlay_scrolling(True)
        # 必须 vexpand：否则 GTK4 ScrolledWindow 只取 min-content-height（默认 46px），
        # 视口裁剪掉第一个模块以下的所有内容
        scroller.set_vexpand(True)

        # 透明度控制已移至设置页，侧边栏底部不再放滑块
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(scroller)

        # 边缘拖拽改宽热区：叠在窗口根上，占 dock 对侧 ~4px 窄条
        overlay = Gtk.Overlay()
        overlay.set_child(outer)
        overlay.add_overlay(self._build_edge_zone())
        # 深色玻璃质感背景（与设置窗口一致；缺此窗口全透明）
        overlay.add_css_class("sb-glass")
        self._font_overlay = overlay
        self._font_provider: Gtk.CssProvider | None = None
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
        self.connect("realize", lambda *_: (self._apply_width(), self._set_x11_window_type()))
        # map 后合成器（Mutter）的初始放置会持续约数秒，期间移动会被覆盖：
        # 在 500ms/2s/5s 各重试一次定位，确保最终位置（贴边或手动坐标）落位
        self.connect("map", self._schedule_redock)
        self._build_context_menu()
        self._build_long_press()

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


    def _tick(self) -> bool:
        self._monitor.last = self._monitor.tick()
        now = time.monotonic()
        for module in getattr(self, "_modules", []):
            try:
                if module.should_update(now):
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
            # 采集频率：模块行设置值（None = 默认 1s）；
            # 倒计时/秒表 UI 必须每秒更新，股票默认 10s 轮询
            if m.type in ("Countdown", "Stopwatch"):
                module.refresh_interval = 1.0
            elif m.type == "Stock":
                module.refresh_interval = m.refresh_interval or 10.0
            else:
                module.refresh_interval = m.refresh_interval or 1.0
            # 模块高度：height_pct > 0 时按侧边栏高度百分比，否则用 base._boxed 的 100px 默认
            if m.height_pct and m.height_pct > 0:
                work_h = self._workarea[3] if hasattr(self, "_workarea") else 100
                window_height = self.store.settings.height or work_h
                widget.set_size_request(-1, int(m.height_pct / 100 * window_height))
            self._modules.append(module)
            self._module_box.append(widget)

