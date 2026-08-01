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

    @abstractmethod
    def build(self) -> Gtk.Widget:
        """构建模块视图，仅调用一次。"""

    def on_tick(self) -> None:
        """每秒轮询钩子（可选重写）。"""

    def on_destroy(self) -> None:
        """清理定时器/连接（可选重写）。"""

    def _boxed(self, child: Gtk.Widget) -> Gtk.Widget:
        """统一包装：固定高度、CSS 类、destroy 钩子。"""
        child.add_css_class("sb-module")
        child.set_size_request(-1, 100)
        child.connect("destroy", lambda *_: self.on_destroy())
        return child
