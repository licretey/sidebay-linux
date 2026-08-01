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
def test_settings_window_header_add_module_and_close_callback(tmp_path):
    from sidebay.settings import SettingsWindow

    store = Store(path=str(tmp_path / "c.json"))
    app = SidebayApplication(store=store)
    app.register()
    closed = []
    win = SettingsWindow(app, store, on_close_callback=lambda: closed.append(True))
    # 自绘暗色头部存在（非 GNOME headerbar）
    root = win.get_child()
    assert root is not None
    header = root.get_first_child()
    assert "sb-settings-header" in header.get_css_classes()
    # 通过列表 API 路径添加模块：下拉选中 → 添加 → store.add → 重建列表
    before = len(store.modules)
    win._type_dropdown.set_selected(2)  # Memory
    win._add_module()
    assert len(store.modules) == before + 1
    assert store.modules[-1].type == "Memory"
    # 关闭 → on-close 回调执行（close-request 只在已映射窗口上发出，故先 present）
    win.present()
    win.close()
    assert closed == [True]
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


@pytest.mark.smoke
def test_opacity_slider_updates_window_and_persists(tmp_path):
    """透明度滑块 → 窗口透明度 + 立即持久化（验收项：透明度滑块生效）。"""
    import json

    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    win._opacity.set_value(0.5)
    # GTK 内部以 0-255 存透明度，0.5 → 128/255，容差取 0.01
    assert abs(win.get_opacity() - 0.5) < 0.01
    assert app.store.settings.opacity == 0.5
    data = json.loads((tmp_path / "c.json").read_text())
    assert data["settings"]["opacity"] == 0.5
    win.destroy()


@pytest.mark.smoke
def test_stock_module_apply_quote_sets_color_class(tmp_path):
    """GTK 4 无 override_color：涨跌色必须走 CSS 类（style.css .sb-stock-up/down）。"""
    from sidebay.modules.stock import StockModule, StockQuote

    store = Store(path=str(tmp_path / "c.json"))
    module = StockModule(store, "stock-test")
    widget = module.build()
    try:
        module._apply_quote(StockQuote(name="X", price="1.00", change_pct="+1%", is_up=True))
        assert "sb-stock-up" in module._price.get_css_classes()
        assert "sb-stock-down" not in module._price.get_css_classes()
        module._apply_quote(StockQuote(name="X", price="1.00", change_pct="-1%", is_up=False))
        assert "sb-stock-down" in module._price.get_css_classes()
        assert "sb-stock-up" not in module._price.get_css_classes()
    finally:
        widget.run_dispose()


@pytest.mark.smoke
def test_all_module_types_build(tmp_path):
    from sidebay.modules.registry import MODULE_TYPES, create_module
    from sidebay.store import Store

    store = Store(path=str(tmp_path / "c.json"))
    widgets = []
    try:
        for type_ in MODULE_TYPES:
            module = create_module(type_, store, f"id-{type_}", monitor=None)
            widget = module.build()
            widgets.append(widget)
            assert widget is not None
    finally:
        for w in widgets:
            w.run_dispose()  # GTK 4.22 无 gtk_widget_destroy，用 run_dispose 触发 destroy 信号
