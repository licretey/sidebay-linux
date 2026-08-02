"""设置窗口：自绘暗色头部 + 通用/模块两页，所有改动立即持久化。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, GObject, Gdk, Gtk

from sidebay.autostart import autostart_enabled, set_autostart
from sidebay.i18n import t
from sidebay.modules.registry import MODULE_TYPES
from sidebay.settings_controls import GeneralControlsMixin
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


class SettingsWindow(Gtk.ApplicationWindow, GeneralControlsMixin):
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
        if hasattr(self, "set_icon_name"):
            self.set_icon_name("org.sidebay.SideBay")

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

        # 采集频率：秒级 + 分钟级（None = 默认 1s）
        freq_options = [(1.0, "1s"), (2.0, "2s"), (5.0, "5s"), (10.0, "10s"),
                        (600.0, "10m"), (1200.0, "20m"), (3600.0, "60m")]
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
