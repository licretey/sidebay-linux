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
    # 不 register：同进程内其他测试已导出同一 D-Bus 对象；且未注册应用创建
    # 窗口在 GTK 4.22 下偶发 gtk_window_set_application 段错误
    closed = []
    win = SettingsWindow(app, store, on_close_callback=lambda: closed.append(True))
    # 自绘标签行：关闭红点 + 下划线标签（非 GNOME headerbar）
    root = win.get_child()
    assert root is not None
    tab_row = root.get_first_child()
    classes = [c.get_css_classes() for c in tab_row.observe_children()] if hasattr(tab_row, "observe_children") else []
    flat = []
    child = tab_row.get_first_child()
    while child is not None:
        flat.append(child.get_css_classes())
        child = child.get_next_sibling()
    assert any("sb-close-native" in c for c in flat), "native close button in tab row"
    assert any("sb-tab" in c for c in flat), "underline tab buttons in tab row"
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
def test_opacity_control_updates_window_and_persists(tmp_path):
    """透明度控制（设置页）→ 窗口透明度 + 立即持久化；侧边栏底部已无滑块。"""
    import json

    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    # 侧边栏底部滑块已移除
    assert not hasattr(win, "_opacity")
    # 模拟设置页透明度控制：直接改 store 并应用（设置页控件同路径）
    app.store.settings.opacity = 0.5
    win._apply_opacity()
    app.store.save()  # 设置页控件处理器同路径：改值 + 立即持久化
    # GTK 内部以 0-255 存透明度，0.5 → 128/255，容差取 0.01
    assert abs(win.get_opacity() - 0.5) < 0.01
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
def test_all_module_types_build(tmp_path, monkeypatch):
    from sidebay.modules.registry import MODULE_TYPES, create_module
    from sidebay.store import Store

    # Stock 模块 build 会启动真实网络线程；测试沙箱的 SSL 握手偶发段错误，
    # 使取数立即失败（走 OSError 分支，不触网）
    def _offline(*_a, **_k):
        raise OSError("offline test")

    monkeypatch.setattr("sidebay.modules.stock.urllib.request.urlopen", _offline)
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


@pytest.mark.smoke
def test_module_height_pct_applies_size_request(tmp_path):
    """M2：height_pct=50 时模块高度请求 ≈ 侧边栏工作区高度的一半。"""
    store = Store(path=str(tmp_path / "c.json"))
    app = SidebayApplication(store=store)
    win = app.create_window()
    try:
        workarea_h = win._workarea[3]
        assert workarea_h > 0
        store.set_height_pct(store.modules[0].module_id, 50.0)
        win.rebuild_modules()
        first = win._module_box.get_first_child()
        assert first is not None
        _, height = first.get_size_request()
        assert abs(height - int(0.5 * workarea_h)) <= 2
    finally:
        win.destroy()


@pytest.mark.smoke
def test_network_arrow_markup_uses_color(tmp_path):
    """SF1：上行绿 #33D966、下行蓝 #5299FF，format_bytes 输出保留。"""
    from sidebay.modules.network import DOWN_COLOR, UP_COLOR, NetworkModule, arrow_markup

    assert arrow_markup("▲", "1 MB/s", UP_COLOR) == '<span foreground="#33D966">▲</span>  1 MB/s'
    assert arrow_markup("▼", "2 MB/s", DOWN_COLOR) == '<span foreground="#5299FF">▼</span>  2 MB/s'

    store = Store(path=str(tmp_path / "c.json"))
    module = NetworkModule(store, "net-test", monitor=None)
    widget = module.build()
    try:
        # 本 GTK 下 get_label 返回原始 markup：可直接断言颜色真实落到了 label 上
        assert '<span foreground="#33D966">▲</span>' in module._up.get_label()
        assert '<span foreground="#5299FF">▼</span>' in module._down.get_label()
        assert "0 B/s" in module._up.get_label()
    finally:
        widget.run_dispose()


@pytest.mark.smoke
def test_calculator_module_button_css_classes(tmp_path):
    """SF2：运算符橙、功能键灰、数字玻璃。"""
    from sidebay.modules.calculator import FUNCTIONS, OPERATORS, CalculatorModule

    store = Store(path=str(tmp_path / "c.json"))
    module = CalculatorModule(store, "calc-test")
    widget = module.build()
    try:
        assert module._buttons
        for btn in module._buttons:
            key = btn.get_label()
            if key in OPERATORS:
                assert "sb-calc-op" in btn.get_css_classes(), key
            elif key in FUNCTIONS:
                assert "sb-calc-fn" in btn.get_css_classes(), key
            else:
                assert "sb-btn-glass" in btn.get_css_classes(), key
    finally:
        widget.run_dispose()


@pytest.mark.smoke
def test_stock_module_invalid_code_shows_error(tmp_path):
    """SF3：请求成功但解析失败（无效代码）→ 显示「无效代码」；网络失败 → 静默。"""
    from sidebay.i18n import t
    from sidebay.modules.stock import FETCH_FAILED, StockModule, StockQuote

    store = Store(path=str(tmp_path / "c.json"))
    module = StockModule(store, "stock-test")
    widget = module.build()
    try:
        module._apply_fetch_result(None)
        assert module._name.get_text() == t("Invalid Code", store.settings.language)
        assert module._price.get_text() == "--"
        assert module._change.get_text() == ""
        module._apply_fetch_result(FETCH_FAILED)  # 网络失败：保持上次显示
        assert module._name.get_text() == t("Invalid Code", store.settings.language)
        module._apply_fetch_result(StockQuote(name="X", price="1.00", change_pct="+1%", is_up=True))
        assert module._name.get_text() == "X"
    finally:
        widget.run_dispose()


@pytest.mark.smoke
def test_settings_close_applies_width_and_position_live(tmp_path):
    """SF4：设置窗口关闭后宽度/位置实时生效（不只重建模块）。"""
    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    app._on_open_settings()
    sw = app.settings_window
    try:
        assert sw is not None
        app.store.settings.width = 150.0
        app.store.settings.position = "right"
        sw._on_close_callback()
        assert app.settings_window is None
        assert win.get_default_size()[0] == 150
    finally:
        if sw is not None:
            sw.destroy()
        win.destroy()


@pytest.mark.smoke
def test_autostart_switch_rolls_back_on_write_failure(tmp_path, monkeypatch):
    """SF7：自启写入失败（OSError）→ 回读磁盘真实状态并对齐开关。"""
    from sidebay.settings import SettingsWindow

    store = Store(path=str(tmp_path / "c.json"))
    app = SidebayApplication(store=store)
    # 不 register：同进程前序测试已导出 /org/sidebay/SideBay，二次注册会 D-Bus 冲突；
    # 本测试不 present 窗口，无需注册
    win = SettingsWindow(app, store, on_close_callback=lambda: None)
    try:
        monkeypatch.setattr("sidebay.settings.set_autostart",
                            lambda _e, _x: (_ for _ in ()).throw(OSError()))
        monkeypatch.setattr("sidebay.autostart.autostart_dir", lambda: tmp_path / "autostart")
        switch = win._autostart_switch
        switch.set_active(False)
        win._on_autostart_toggled(switch, True)  # 用户开启但写入失败
        assert switch.get_active() is False      # 磁盘无文件 → 开关保持关闭
        assert store.settings.launch_at_login is False
        # 成功路径：持久化
        monkeypatch.setattr("sidebay.settings.set_autostart", lambda _e, _x: None)
        win._on_autostart_toggled(switch, True)
        assert store.settings.launch_at_login is True
    finally:
        win.destroy()


@pytest.mark.smoke
def test_style_css_defines_smoke_classes():
    """SF2/SF9：模块引用的 CSS 类必须在 style.css 中定义。"""
    from pathlib import Path

    css = Path(__file__).resolve().parent.parent / "sidebay" / "style.css"
    text = css.read_text()
    for cls in (".sb-calc-op", ".sb-calc-fn", ".sb-edge-zone", ".sb-stock-up", ".sb-stock-down"):
        assert cls in text


@pytest.mark.smoke
def test_sidebar_scroller_expands_and_has_glass(tmp_path):
    """回归：ScrolledWindow 必须 vexpand（否则视口 46px 裁剪掉首模块以下内容）；
    主窗口必须带 sb-glass 玻璃背景类（否则全透明）。"""
    from sidebay.app import SidebayApplication
    from sidebay.store import Store

    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    try:
        overlay = win.get_child()
        assert overlay.get_css_classes(), "sidebar root should have css classes"
        assert "sb-glass" in overlay.get_css_classes()
        # overlay 主 child = VBox(scroller + slider)
        vbox = overlay.get_first_child()
        scroller = vbox.get_first_child()
        assert scroller.get_vexpand(), "scroller must vexpand so modules are not clipped"
    finally:
        win.run_dispose()


@pytest.mark.smoke
def test_long_press_opens_settings(tmp_path):
    """回归：按住侧边栏 1.5s 打开设置窗口（GTK4 GestureClick 内置长按检测
    会提前发 stopped，不得用 stopped 取消定时器）。无 X11/XTEST 时跳过。"""
    import os
    import time

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display for synthetic events")

    from Xlib import X, display as xd
    from Xlib.ext import xtest

    from sidebay.app import SidebayApplication
    from sidebay.store import Store
    from sidebay.window import SidebarWindow

    # 不 register（同进程内其他测试已导出同一 application_id 的 D-Bus 对象，
    # 且未注册时 activate_action 无法解析 "app." 动作）。
    # 因此只验证 手势→定时器→_on_long_press 链路，动作调用本身由他处覆盖。
    fired = []
    orig_long_press = SidebarWindow._on_long_press

    def patched_long_press(self):
        fired.append(True)
        return False

    SidebarWindow._on_long_press = patched_long_press
    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    win.present()
    try:
        # 等待映射并让事件循环跑起来
        for _ in range(20):
            while GLib.MainContext.default().iteration(False):
                pass
            time.sleep(0.05)

        d = xd.Display()
        from gi.repository import GdkX11
        native = win.get_native()
        surf = native.get_surface()
        xid = surf.get_xid()
        g = d.create_resource_object("window", xid).get_geometry()
        root = d.screen().root
        tx, ty = g.x + g.width // 2, g.y + 300
        root.warp_pointer(tx, ty)
        d.sync()
        xtest.fake_input(d, X.ButtonPress, 1)
        d.sync()
        # 按住 1.8s > 1.5s 阈值
        end = time.monotonic() + 1.8
        while time.monotonic() < end:
            while GLib.MainContext.default().iteration(False):
                pass
            time.sleep(0.05)
        xtest.fake_input(d, X.ButtonRelease, 1)
        d.sync()
        for _ in range(10):
            while GLib.MainContext.default().iteration(False):
                pass
            time.sleep(0.05)
        assert fired, "long-press should trigger _on_long_press after 1.5s hold"
    finally:
        SidebarWindow._on_long_press = orig_long_press
        win.run_dispose()
