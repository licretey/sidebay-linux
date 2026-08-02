"""设置窗口通用页控件（GeneralControlsMixin）。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, GObject, Gdk, Gtk

from sidebay.autostart import autostart_enabled, set_autostart
from sidebay.i18n import t

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


class GeneralControlsMixin:
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
