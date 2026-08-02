"""模块基类：统一接口，build() 返回 Gtk.Widget。"""

from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from sidebay.store import Store


class Module(ABC):
    def __init__(self, store: Store, module_id: str):
        self.store = store
        self.module_id = module_id
        self.refresh_interval = 1.0  # 采集频率（秒），由窗口 tick 按此节流
        self._last_update = 0.0

    @abstractmethod
    def build(self) -> Gtk.Widget:
        """构建模块视图，仅调用一次。"""

    def on_tick(self) -> None:
        """轮询钩子（按 refresh_interval 节流调用，默认 1s）。"""

    def on_destroy(self) -> None:
        """清理定时器/连接（可选重写）。"""

    @staticmethod
    def make_title(text: str) -> Gtk.Label:
        """模块标题（统一 sb-module-title 样式）。"""
        label = Gtk.Label(label=text)
        label.add_css_class("sb-module-title")
        return label

    @staticmethod
    def make_value_label(css: str = "sb-tick-label") -> Gtk.Label:
        """数值标签（统一 sb-tick-label 样式）。"""
        label = Gtk.Label()
        label.add_css_class(css)
        return label

    def should_update(self, now: float) -> bool:
        """窗口 tick（1s）按模块频率节流：到期才调用 on_tick。"""
        if now - self._last_update >= self.refresh_interval:
            self._last_update = now
            return True
        return False

    def _boxed(self, child: Gtk.Widget) -> Gtk.Widget:
        """统一包装：固定高度、CSS 类、destroy 钩子。"""
        child.add_css_class("sb-module")
        child.set_size_request(-1, 100)
        child.connect("destroy", lambda *_: self.on_destroy())
        return child
