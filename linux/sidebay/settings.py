"""设置窗口：自绘暗色头部 + 通用/模块两页，所有改动立即持久化。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, GObject, Gdk, Gtk

from sidebay.autostart import set_autostart
from sidebay.i18n import t
from sidebay.modules.registry import MODULE_TYPES
from sidebay.store import AppModule

DEFAULT_EXEC_LINE = "flatpak run org.sidebay.SideBay"

_LANGS = ["中文", "English"]


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store, on_close_callback, exec_line: str = DEFAULT_EXEC_LINE):
        super().__init__(application=app)
        self.store = store
        self._on_close_callback = on_close_callback
        self._exec_line = exec_line
        self._drag_start_width = 0
        self.set_decorated(False)
        self.set_default_size(480, 420)
        self.set_resizable(False)
        self.set_title("Sidebay Settings")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("sb-glass")
        root.append(self._build_header())
        notebook = Gtk.Notebook()
        notebook.append_page(self._build_general(), Gtk.Label(label="通用"))
        notebook.append_page(self._build_modules(), Gtk.Label(label="模块"))
        root.append(notebook)
        self.set_child(root)
        self.connect("close-request", lambda *_: self._on_close())

    # ---------- 头部 ----------

    def _build_header(self) -> Gtk.Box:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("sb-settings-header")
        title = Gtk.Label(label=t("SettingsTitle", self.store.settings.language))
        title.set_halign(Gtk.Align.START)
        header.append(title)
        close = Gtk.Button()
        close.add_css_class("sb-settings-close")
        close.set_halign(Gtk.Align.END)
        close.set_hexpand(True)
        close.connect("clicked", lambda *_: self.close())
        header.append(close)
        return header

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

        # 开机自启
        self._autostart_switch = Gtk.Switch()
        self._autostart_switch.set_active(self.store.settings.launch_at_login)
        self._autostart_switch.set_valign(Gtk.Align.CENTER)
        self._autostart_switch.connect("state-set", self._on_autostart_toggled)
        page.append(self._row(t("Launch at Login", lang), self._autostart_switch))
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

    def _on_autostart_toggled(self, switch: Gtk.Switch, state: bool) -> bool:
        try:
            set_autostart(bool(state), self._exec_line)
        except OSError:
            return False
        self.store.settings.launch_at_login = bool(state)
        self.store.save()
        return False

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
