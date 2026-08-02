"""顶部面板托盘图标（StatusNotifierItem / DBusMenu）。

GNOME 需 AppIndicator 扩展（appindicatorsupport）提供 StatusNotifierWatcher；
无 watcher 时静默降级（不显示图标，应用照常运行）。
菜单：显示/隐藏、设置、退出。
"""

from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
WATCHER_IFACE = "org.kde.StatusNotifierWatcher"
APP_ID = "org.sidebay.SideBay"

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <method name="Activate"/>
    <method name="SecondaryActivate"/>
    <method name="ContextMenu"/>
  </interface>
</node>
"""

INTROSPECT_XML = """
<node>
  <interface name="org.freedesktop.DBus.Introspectable">
    <method name="Introspect"><arg type="s" direction="out"/></method>
  </interface>
</node>
"""

# Introspect 返回的完整节点 XML：含 SNI（无参方法 + 属性）与 Properties
_INTROSPECT_NODE_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <method name="Activate"/>
    <method name="SecondaryActivate"/>
    <method name="ContextMenu"/>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
    <method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
  </interface>
</node>
"""

PROPS_XML = """
<node>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
    <method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/><arg type="u" name="revision" direction="out"/><arg type="(ia{sv}av)" name="layout" direction="out"/></method>
    <method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/></method>
    <method name="GetProperty"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
    <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
    <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="u" direction="out"/></method>
    <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
    <method name="AboutToShowGroup"><arg type="ai" direction="in"/><arg type="ai" direction="out"/></method>
  </interface>
</node>
"""


class TrayIcon:
    """在顶部面板显示 Sidebay 图标；无 watcher 时静默降级。"""

    def __init__(self, app):
        self._app = app
        self._conn: Gio.DBusConnection | None = None
        self.registered = False
        self._visible = True
        self._pixmap = self._load_pixmap()
        # 菜单项：(id, key, 动态 label 回调)
        self._items = [
            (1, "toggle", self._toggle_label),
            (2, "settings", lambda: "设置"),
            (3, "quit", lambda: "退出"),
        ]

    def _toggle_label(self) -> str:
        if getattr(self._app, "window", None) is None:
            return "显示侧边栏"
        return "隐藏侧边栏" if self._visible else "显示侧边栏"

    # ---------- 启动 ----------

    def start(self) -> bool:
        try:
            self._conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self._register_objects()
            self._register_with_watcher()
            self.registered = True
            return True
        except Exception:
            self._conn = None
            self.registered = False
            return False

    def _register_objects(self) -> None:
        for path, xml in ((SNI_PATH, SNI_XML), (SNI_PATH, PROPS_XML), (SNI_PATH, INTROSPECT_XML),
                          (MENU_PATH, MENU_XML), (MENU_PATH, INTROSPECT_XML)):
            node = Gio.DBusNodeInfo.new_for_xml(xml)
            self._conn.register_object(
                path,
                node.interfaces[0],
                self._on_method_call,
                None,
                None,
            )

    def _register_with_watcher(self) -> None:
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            None,
            WATCHER_NAME,
            WATCHER_PATH,
            WATCHER_IFACE,
            None,
        )
        # 传唯一名（非 well-known 名），watcher 直接回调我们的对象
        proxy.call_sync(
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self._conn.get_unique_name(),)),
            Gio.DBusCallFlags.NONE,
            2000,
            None,
        )

    # ---------- SNI 属性 ----------

    def _props(self) -> dict:
        return {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "sidebay"),
            "Title": GLib.Variant("s", "Sidebay"),
            "Status": GLib.Variant("s", "Active"),
            "IconName": GLib.Variant("s", APP_ID),
            "IconPixmap": GLib.Variant("a(iiay)", self._pixmap),
            "Menu": GLib.Variant("o", MENU_PATH),
            # 关键：ItemIsMenu=true 让主机把图标视为菜单项——左键直接弹菜单
            # （否则主机走 Activate，而我们按用户要求左键无操作 → 点击无响应）
            "ItemIsMenu": GLib.Variant("b", True),
        }

    @staticmethod
    def _load_pixmap() -> list:
        """从 logos/sidebay-512.png 读 22px 图标（RGBA → ARGB32 紧密打包）。"""
        try:
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf

            logo = Path(__file__).resolve().parent.parent / "logos" / "sidebay-512.png"
            if not logo.exists():
                return []
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(logo), 22, 22, True)
            pixels = pb.get_pixels()
            rowstride = pb.get_rowstride()
            w, h = pb.get_width(), pb.get_height()
            data = bytearray()
            for y in range(h):
                row = pixels[y * rowstride:(y + 1) * rowstride]
                for x in range(w):
                    r, g, b, a = row[x * 4], row[x * 4 + 1], row[x * 4 + 2], row[x * 4 + 3]
                    data += bytes((a, r, g, b))  # ARGB32 大端
            return [(w, h, bytes(data))]
        except Exception:
            return []

    # ---------- 方法分发 ----------

    def _on_method_call(self, conn, sender, path, iface, method, params, invocation):
        try:
            if iface == "org.freedesktop.DBus.Properties":
                self._on_properties(method, params, invocation)
            elif iface == "org.kde.StatusNotifierItem":
                self._on_sni(method, invocation)
            elif iface == "com.canonical.dbusmenu":
                self._on_menu(method, params, invocation)
            elif iface == "org.freedesktop.DBus.Introspectable":
                # AppIndicator 扩展经 Introspect 探测我们是否支持 Activate
                invocation.return_value(GLib.Variant("(s)", (_INTROSPECT_NODE_XML,)))
            else:
                invocation.return_error_literal(
                    Gio.DBusError.NOT_SUPPORTED, f"unknown interface {iface}")
        except Exception as e:
            invocation.return_error_literal(Gio.DBusError.FAILED, str(e))

    def _on_properties(self, method, params, invocation) -> None:
        if method == "Get":
            prop = params[1]
            value = self._props().get(prop)
            if value is None:
                invocation.return_error_literal(Gio.DBusError.INVALID_ARGS, f"no {prop}")
            else:
                invocation.return_value(GLib.Variant("(v)", (value,)))
        elif method == "GetAll":
            invocation.return_value(GLib.Variant("(a{sv})", (self._props(),)))
        else:
            invocation.return_error_literal(Gio.DBusError.NOT_SUPPORTED, method)

    def _on_sni(self, method, invocation) -> None:
        if method == "Activate":
            # 左键不操作：全部交互走右键菜单
            invocation.return_value(None)
        elif method in ("SecondaryActivate", "ContextMenu"):
            invocation.return_value(None)
        else:
            invocation.return_error_literal(Gio.DBusError.NOT_SUPPORTED, method)

    def _on_menu(self, method, params, invocation) -> None:
        if method == "GetLayout":
            items = []
            for item_id, key, label in self._items:
                props = {
                    "label": GLib.Variant("s", label()),
                    "enabled": GLib.Variant("b", True),
                    "visible": GLib.Variant("b", True),
                }
                items.append(GLib.Variant("(ia{sv}av)", (item_id, props, [])))
            # 官方 com.canonical.dbusmenu 规范：GetLayout 返回 (u revision, (ia{sv}av) layout)
            # ——AppIndicator 扩展按此解构 [revision, root]，缺 revision 会导致解析失败
            reply = GLib.Variant("(u(ia{sv}av))", (0, (0, {}, items)))
            invocation.return_value(reply)
        elif method == "GetGroupProperties":
            # 返回空属性集即可（AppIndicator 会按需 GetProperty/GetLayout）
            invocation.return_value(GLib.Variant("(a(ia{sv}))", ([])))
        elif method == "GetProperty":
            invocation.return_value(GLib.Variant("(v)", (GLib.Variant("s", ""),)))
        elif method == "Event":
            item_id = params[0] if params and params.get_n_children() > 0 else -1
            if isinstance(item_id, int):
                self._on_menu_click(item_id)
            invocation.return_value(None)
        elif method in ("EventGroup", "AboutToShow", "AboutToShowGroup"):
            invocation.return_value(GLib.Variant("(u)", (0,)) if method == "EventGroup"
                                    else GLib.Variant("(b)", (True,)) if method == "AboutToShow"
                                    else GLib.Variant("(ai)", ([],)))
        else:
            invocation.return_error_literal(Gio.DBusError.NOT_SUPPORTED, method)

    # ---------- 动作 ----------

    def _on_menu_click(self, item_id: int) -> None:
        for iid, key, _label in self._items:
            if iid == item_id:
                if key == "toggle":
                    self._toggle()
                elif key == "settings":
                    self._app.activate_action("app.open-settings", None)
                elif key == "quit":
                    self._app.quit()
                return

    def _toggle(self) -> None:
        win = getattr(self._app, "window", None)
        if win is None:
            # 启动时不建窗口（无 Dock 痕迹）：首次呼出时懒创建
            self._app.create_window()
            self._visible = True
            return
        self._visible = not self._visible
        if self._visible:
            win.present()
        else:
            win.set_visible(False)
