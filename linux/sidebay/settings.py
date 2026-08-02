"""设置窗口：自绘暗色头部 + 通用/模块两页，所有改动立即持久化。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, GObject, Gdk, Gtk

from sidebay.autostart import autostart_enabled, set_autostart
from sidebay.i18n import t
from sidebay.modules.registry import MODULE_TYPES
from sidebay.store import AppModule

DEFAULT_EXEC_LINE = "flatpak run org.sidebay.SideBay"

_LANGS = ["中文", "English"]
_FONT_SIZES = [("小", "small"), ("中", "medium"), ("大", "large")]
_FONT_FAMILIES = [
    ("系统默认", ""),
    ("Cantarell", "Cantarell"),
    ("Noto Sans CJK SC", "Noto Sans CJK SC"),
    ("WenQuanYi Micro Hei", "WenQuanYi Micro Hei"),
    ("Liberation Sans", "Liberation Sans"),
    ("等宽 monospace", "monospace"),
]


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store, on_close_callback, exec_line: str = DEFAULT_EXEC_LINE,
                 on_position_change=None, on_style_change=None):
        super().__init__(application=app)
        self.store = store
        self._on_close_callback = on_close_callback
        self._exec_line = exec_line
        self._on_position_change = on_position_change
        self._on_style_change = on_style_change
        self._drag_start_width = 0
        self.set_decorated(False)
        self.set_default_size(480, 420)
        self.set_resizable(False)
        self.set_title("Sidebay Settings")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("sb-glass")
        self._notebook = Gtk.Notebook()
        self._notebook.append_page(self._build_general(), Gtk.Label(label="通用"))
        self._notebook.append_page(self._build_modules(), Gtk.Label(label="模块"))
        self._notebook.set_show_tabs(False)  # 标签行自绘：关闭按钮 + 通用/模块同一行
        root.append(self._build_tab_row())
        root.append(self._notebook)
        self.set_child(root)
        self._font_provider: Gtk.CssProvider | None = None
        self._apply_self_font()
        self.connect("close-request", lambda *_: self._on_close())

    def _apply_self_font(self) -> None:
        """设置窗口自身反映字号/字体选择（与侧边栏 apply_font_style 一致）。"""
        size = self.store.settings.font_size or "medium"
        if size != "medium":
            self.get_child().add_css_class(f"sb-font-{size}")
        if self._font_provider is not None:
            self.get_style_context().remove_provider(self._font_provider)
            self._font_provider = None
        family = self.store.settings.font_family
        if family:
            self._font_provider = Gtk.CssProvider()
            self._font_provider.load_from_string(f"* {{ font-family: '{family}'; }}")
            self.get_style_context().add_provider(self._font_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # ---------- 标签行（关闭按钮 + 通用/模块，同一行） ----------

    def _build_tab_row(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        # 无顶部标题条：下划线标签在左，关闭按钮在右（原生圆形 ×）
        row.set_margin_top(8)
        row.set_margin_bottom(2)
        row.set_margin_start(10)
        row.set_margin_end(10)

        self._tab_general = self._tab_button("通用", 0)
        self._tab_modules = self._tab_button("模块", 1)
        # radio 互斥：激活一个自动取消另一个，只有激活标签显示下划线
        self._tab_modules.set_group(self._tab_general)
        row.append(self._tab_general)
        row.append(self._tab_modules)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        row.append(spacer)

        close = Gtk.Button()
        close.add_css_class("sb-close-native")
        close.set_valign(Gtk.Align.CENTER)
        close.set_child(Gtk.Label(label="✕"))
        close.connect("clicked", lambda *_: self.close())
        row.append(close)
        return row

    def _tab_button(self, label: str, page: int) -> Gtk.Button:
        button = Gtk.ToggleButton(label=label)
        button.add_css_class("sb-tab")
        button.set_active(page == 0)
        button.connect("toggled", self._on_tab_toggled, page)
        return button

    def _on_tab_toggled(self, button: Gtk.ToggleButton, page: int) -> None:
        if button.get_active():
            self._notebook.set_current_page(page)

    # ---------- 通用页 ----------

    def _build_general(self) -> Gtk.Box:
        lang = self.store.settings.language
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(16)
        page.set_margin_bottom(16)
        page.set_margin_start(16)
        page.set_margin_end(16)

        # 语言
        self._lang_dropdown = Gtk.DropDown(model=Gtk.StringList.new(_LANGS))
        self._lang_dropdown.set_selected(0 if lang == "zh" else 1)
        self._lang_dropdown.connect("notify::selected", self._on_language_changed)
        page.append(self._row(t("Language", lang), self._lang_dropdown))

        # 位置
        self._position_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new([t("Left", lang), t("Right", lang)]))
        self._position_dropdown.set_selected(0 if self.store.settings.position == "left" else 1)
        self._position_dropdown.connect("notify::selected", self._on_position_changed)
        page.append(self._row(t("Position", lang), self._position_dropdown))

        # 宽度滑块（40-300）+ 当前值
        width_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._width_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._width_scale.set_range(40, 300)
        current = self.store.settings.width if self.store.settings.width > 0 else 100
        self._width_scale.set_value(current)
        self._width_scale.set_hexpand(True)
        self._width_scale.connect("value-changed", self._on_width_changed)
        width_box.append(self._width_scale)
        self._width_value = Gtk.Label(label=f"{int(current)}")
        self._width_value.add_css_class("sb-tick-label")
        width_box.append(self._width_value)
        page.append(self._row(t("Width", lang), width_box))

        # 手动位置 X / Y（左上角坐标；实时移动窗口）
        xy_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._pos_x_spin = Gtk.SpinButton.new_with_range(0, 8192, 1)
        self._pos_x_spin.set_value(self.store.settings.pos_x or 0)
        self._pos_x_spin.set_width_chars(5)
        self._pos_x_spin.connect("value-changed", self._on_pos_x_changed)
        xy_box.append(self._pos_x_spin)
        self._pos_y_spin = Gtk.SpinButton.new_with_range(0, 4096, 1)
        self._pos_y_spin.set_value(self.store.settings.pos_y or 0)
        self._pos_y_spin.set_width_chars(5)
        self._pos_y_spin.connect("value-changed", self._on_pos_y_changed)
        xy_box.append(self._pos_y_spin)
        # 提示：X/Y 均可实时移动（默认自动 XWayland；全高窗口下移会超屏被钳回，配高度控件使用）
        y_hint = Gtk.Label(label="(X/Y 实时移动)")
        y_hint.add_css_class("sb-tick-label")
        y_hint.set_opacity(0.6)
        y_hint.set_tooltip_text("X/Y 实时移动；窗口设短（高度控件）后任意位置可达")
        xy_box.append(y_hint)
        page.append(self._row(t("Position", lang) + " X/Y", xy_box))

        # 窗口高度（None = 全屏高度；设置后为短条，内容滚动）
        self._height_spin = Gtk.SpinButton.new_with_range(100, 4096, 10)
        self._height_spin.set_value(self.store.settings.height or 1440)
        self._height_spin.set_width_chars(5)
        self._height_spin.connect("value-changed", self._on_height_changed)
        page.append(self._row("高度", self._height_spin))

        # 字号
        self._font_size_dropdown = Gtk.DropDown(model=Gtk.StringList.new([s for s, _ in _FONT_SIZES]))
        current_size = self.store.settings.font_size or "medium"
        self._font_size_dropdown.set_selected(next((i for i, (_, v) in enumerate(_FONT_SIZES) if v == current_size), 1))
        self._font_size_dropdown.connect("notify::selected", self._on_font_size_changed)
        page.append(self._row("字号", self._font_size_dropdown))

        # 字体族
        self._font_family_dropdown = Gtk.DropDown(model=Gtk.StringList.new([n for n, _ in _FONT_FAMILIES]))
        current_family = self.store.settings.font_family
        self._font_family_dropdown.set_selected(next((i for i, (_, v) in enumerate(_FONT_FAMILIES) if v == current_family), 0))
        self._font_family_dropdown.connect("notify::selected", self._on_font_family_changed)
        page.append(self._row("字体", self._font_family_dropdown))

        # 背景透明度（与侧边栏底部滑块共用 store.settings.opacity）
        self._opacity_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._opacity_scale.set_range(0.1, 1.0)
        self._opacity_scale.set_value(self.store.settings.opacity)
        self._opacity_scale.set_hexpand(True)
        self._opacity_scale.connect("value-changed", self._on_opacity_changed)
        page.append(self._row("透明度", self._opacity_scale))

        # 开机自启
        self._autostart_switch = Gtk.Switch()
        self._autostart_switch.set_active(self.store.settings.launch_at_login)
        self._autostart_switch.set_valign(Gtk.Align.CENTER)
        self._autostart_switch.connect("state-set", self._on_autostart_toggled)
        page.append(self._row(t("Launch at Login", lang), self._autostart_switch))
        # _row 默认给控件 hexpand，会把开关横向拉伸变形；改为自然宽度靠右
        self._autostart_switch.set_hexpand(False)
        self._autostart_switch.set_halign(Gtk.Align.END)
        return page

    @staticmethod
    def _row(label_text: str, control: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.START)
        label.set_size_request(140, -1)
        row.append(label)
        control.set_hexpand(True)
        row.append(control)
        return row

    def _on_language_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        lang = "zh" if dropdown.get_selected() == 0 else "en"
        if lang == self.store.settings.language:
            return
        self.store.settings.language = lang
        self.store.save()

    def _on_position_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        position = "left" if dropdown.get_selected() == 0 else "right"
        if position == self.store.settings.position:
            return
        self.store.settings.position = position
        self.store.save()

    def _on_width_changed(self, scale: Gtk.Scale) -> None:
        value = int(scale.get_value())
        self._width_value.set_text(f"{value}")
        if value == self.store.settings.width:
            return
        self.store.settings.width = float(value)
        self.store.save()
        # 宽度独立即时生效（此前仅在高度变化/关闭设置时随 _apply_width 触发）
        if self._on_style_change is not None:
            self._on_style_change()

    def _on_autostart_toggled(self, switch: Gtk.Switch, state: bool) -> bool:
        try:
            set_autostart(bool(state), self._exec_line)
        except OSError:
            # 写入失败：回读磁盘真实状态并让开关与之对齐（GTK4 state-set 返回值语义含糊，不依赖它）
            switch.set_active(autostart_enabled())
            return True
        self.store.settings.launch_at_login = bool(state)
        self.store.save()
        return False

    def _on_pos_x_changed(self, spin: Gtk.SpinButton) -> None:
        self.store.settings.pos_x = float(spin.get_value())
        self.store.save()
        if self._on_position_change is not None and self.store.settings.pos_y is not None:
            self._on_position_change(self.store.settings.pos_x, self.store.settings.pos_y)

    def _on_pos_y_changed(self, spin: Gtk.SpinButton) -> None:
        self.store.settings.pos_y = float(spin.get_value())
        self.store.save()
        if self._on_position_change is not None and self.store.settings.pos_x is not None:
            self._on_position_change(self.store.settings.pos_x, self.store.settings.pos_y)

    def _on_height_changed(self, spin: Gtk.SpinButton) -> None:
        self.store.settings.height = float(spin.get_value())
        self.store.save()
        if self._on_style_change is not None:
            self._on_style_change()

    def _on_font_size_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        _, value = _FONT_SIZES[dropdown.get_selected()]
        self.store.settings.font_size = value
        self.store.save()
        self._apply_self_font()
        if self._on_style_change is not None:
            self._on_style_change()

    def _on_font_family_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        _, value = _FONT_FAMILIES[dropdown.get_selected()]
        self.store.settings.font_family = value
        self.store.save()
        self._apply_self_font()
        if self._on_style_change is not None:
            self._on_style_change()

    def _on_opacity_changed(self, scale: Gtk.Scale) -> None:
        value = scale.get_value()
        self.store.settings.opacity = value
        self.store.save()
        if self._on_style_change is not None:
            self._on_style_change()

    # ---------- 模块页 ----------

    def _build_modules(self) -> Gtk.Box:
        lang = self.store.settings.language
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_margin_top(16)
        page.set_margin_bottom(16)
        page.set_margin_start(16)
        page.set_margin_end(16)

        hint = Gtk.Label(label=t("Hint", lang))
        hint.set_halign(Gtk.Align.START)
        hint.add_css_class("sb-tick-label")
        page.append(hint)

        self._module_list = Gtk.ListBox()
        self._module_list.set_selection_mode(Gtk.SelectionMode.NONE)
        target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        target.connect("drop", self._on_drop)
        self._module_list.add_controller(target)
        page.append(self._module_list)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._type_dropdown = Gtk.DropDown(model=Gtk.StringList.new(MODULE_TYPES))
        add_btn = Gtk.Button(label=t("Add", lang))
        add_btn.add_css_class("sb-btn-glass")
        add_btn.connect("clicked", self._add_module)
        bottom.append(self._type_dropdown)
        bottom.append(add_btn)
        page.append(bottom)

        self._rebuild_module_list()
        return page

    def _make_row(self, m: AppModule) -> Gtk.ListBoxRow:
        lang = self.store.settings.language
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        handle = Gtk.Label(label="⋮⋮")
        handle.add_css_class("sb-tick-label")
        box.append(handle)

        name = Gtk.Label(label=t(m.type, lang))
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        box.append(name)

        if m.type == "Stock":
            entry = Gtk.Entry()
            entry.set_text(m.custom_data or "")
            entry.set_placeholder_text("600519")
            entry.connect("changed",
                          lambda e, mid=m.module_id: self.store.set_custom_data(mid, e.get_text()))
            box.append(entry)

        spin = Gtk.SpinButton.new_with_range(0, 100, 1)
        spin.set_value(m.height_pct or 0)
        spin.connect("value-changed",
                     lambda sb, mid=m.module_id: self.store.set_height_pct(mid, sb.get_value()))
        box.append(spin)

        # 采集频率：1/2/5/10 秒（None = 默认 1s）
        freq_options = [(1.0, "1s"), (2.0, "2s"), (5.0, "5s"), (10.0, "10s")]
        freq = Gtk.DropDown(model=Gtk.StringList.new([l for _, l in freq_options]))
        current_freq = m.refresh_interval or 1.0
        freq.set_selected(next((i for i, (v, _) in enumerate(freq_options) if v == current_freq), 0))
        freq.connect("notify::selected",
                     lambda dd, mid=m.module_id, opts=freq_options:
                     self.store.set_refresh_interval(mid, float(opts[dd.get_selected()][0])))
        freq.set_tooltip_text("采集频率")
        box.append(freq)

        delete = Gtk.Button(label="🗑")
        delete.add_css_class("sb-settings-close")
        delete.connect("clicked", lambda *_, mid=m.module_id: self._remove_module(mid))
        box.append(delete)

        source = Gtk.DragSource()
        source.set_actions(Gdk.DragAction.MOVE)
        source.connect("prepare",
                       lambda _s, _x, _y, mid=m.module_id: Gdk.ContentProvider.new_for_value(mid))
        row.add_controller(source)
        row.set_child(box)
        return row

    def _rebuild_module_list(self) -> None:
        if not hasattr(self, "_module_list"):
            return
        while (child := self._module_list.get_first_child()) is not None:
            self._module_list.remove(child)
        for m in self.store.modules:
            self._module_list.append(self._make_row(m))

    def _add_module(self, *_a) -> None:
        item = self._type_dropdown.get_selected_item()
        type_ = item.get_string() if item is not None else MODULE_TYPES[0]
        self.store.add(type_)
        self._rebuild_module_list()

    def _remove_module(self, module_id: str) -> None:
        self.store.remove(module_id)
        self._rebuild_module_list()

    def _on_drop(self, target: Gtk.DropTarget, value, x: float, y: float) -> bool:
        if not isinstance(value, str):
            return False
        from_index = next((i for i, m in enumerate(self.store.modules)
                           if m.module_id == value), None)
        if from_index is None:
            return False
        row = self._module_list.get_row_at_y(y)
        to_index = row.get_index() if row is not None else len(self.store.modules) - 1
        self.store.move(from_index, to_index)
        # 拖拽完成后（idle）再重建列表，避免在 drop 处理中销毁拖拽源行
        GLib.idle_add(self._rebuild_module_list)
        return True

    # ---------- 关闭 ----------

    def _on_close(self):
        self._on_close_callback()
        return False
