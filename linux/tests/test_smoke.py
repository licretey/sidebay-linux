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


@pytest.mark.smoke
def test_keyboard_capture_xrecord(tmp_path):
    """XTest 合成按键 → XRecord 回调 → label 更新（无 X/python-xlib 时跳过）。"""
    import os
    import time
    import warnings

    pytest.importorskip("Xlib")
    if "DISPLAY" not in os.environ:
        pytest.skip("no X11 display")
    # gi/events.py 在每次 pump 时触发 asyncio 弃用告警（Python 3.14 环境噪音）
    warnings.filterwarnings("ignore", message=".*get_event_loop_policy.*")
    from gi.repository import GLib

    from Xlib import X, XK, display as xdisplay

    from sidebay.modules.keyboard import KeyboardModule
    from sidebay.store import Store

    store = Store(path=str(tmp_path / "c.json"))
    module = KeyboardModule(store, "kb-test")
    widget = module.build()
    try:
        if module._listener is None:
            pytest.skip("XRecord 不可用（无 RECORD 扩展或 X 连接失败）")
        # 需要带事件掩码的聚焦窗口，Xvfb 才会投递/记录按键事件
        dpy = xdisplay.Display()
        root = dpy.screen().root
        win = root.create_window(0, 0, 100, 100, 0, dpy.screen().root_depth)
        win.map()
        dpy.sync()
        dpy.set_input_focus(win, X.RevertToParent, X.CurrentTime)
        win.change_attributes(event_mask=X.KeyPressMask)
        dpy.sync()
        keycode = dpy.keysym_to_keycode(XK.string_to_keysym("a"))
        assert keycode, "keycode for 'a' not found"
        # 循环发送合成按键并泵 GLib；窗口收到按键但模块未捕获才算失败，
        # X 服务器完全无法投递（XTEST 不可用/焦点被 WM 接管）则跳过
        module._label.set_text(" ")
        got_key = False
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and module._label.get_text() in ("", " "):
            dpy.xtest_fake_input(X.KeyPress, keycode)
            dpy.xtest_fake_input(X.KeyRelease, keycode)
            dpy.flush()
            sub = time.monotonic() + 0.15
            while time.monotonic() < sub:
                while dpy.pending_events():
                    if dpy.next_event().type == X.KeyPress:
                        got_key = True
                GLib.MainContext.default().iteration(False)
                if module._label.get_text() not in ("", " "):
                    break
                time.sleep(0.005)
        if module._label.get_text() in ("", " "):
            if got_key:
                pytest.fail("按键已投递但模块未捕获")
            pytest.skip("X 服务器未投递 XTest 合成按键")
    finally:
        widget.run_dispose()
