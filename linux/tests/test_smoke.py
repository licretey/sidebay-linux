import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from sidebay.app import SidebayApplication
from sidebay.store import Store


@pytest.mark.smoke
def test_app_creates_sidebar_window(tmp_path):
    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    assert isinstance(win, Gtk.Window)
    assert not win.get_decorated()
    win.destroy()


@pytest.mark.smoke
def test_rebuild_modules_creates_widgets(tmp_path):
    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    win.rebuild_modules()
    box = win._module_box  # 测试只读内部挂载点
    assert box.get_first_child() is not None
    win.destroy()


@pytest.mark.smoke
def test_keyboard_module_builds_without_x(tmp_path):
    from sidebay.modules.keyboard import KeyboardModule
    from sidebay.store import Store

    store = Store(path=str(tmp_path / "c.json"))
    module = KeyboardModule(store, "kb-test")
    widget = module.build()  # 无 DISPLAY 时也不得抛错
    assert widget is not None
    widget.run_dispose()  # GTK 4.22 无 gtk_widget_destroy，用 run_dispose 触发 destroy 信号
