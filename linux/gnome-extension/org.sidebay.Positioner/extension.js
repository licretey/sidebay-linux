/* Sidebay Positioner — GNOME Shell 扩展（GNOME 45+ ESM）。
 *
 * 目的：GNOME Wayland 下客户端（含 XWayland）无法控制窗口垂直位置
 * （合成器将窗口顶边钉在 y=0）。本扩展在会话总线导出
 * org.sidebay.Positioner 接口，Sidebay 应用经 D-Bus 请求
 * MetaWindow.move_resize_frame 实现任意 X/Y 定位。
 */

import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const IFACE_XML = `
<node>
  <interface name="org.sidebay.Positioner">
    <method name="MoveWindow">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
      <arg type="i" name="width" direction="in"/>
      <arg type="i" name="height" direction="in"/>
    </method>
    <method name="GetWindowInfo">
      <arg type="(iiii)" name="info" direction="out"/>
    </method>
  </interface>
</node>`;

export default class SidebayPositionerExtension extends Extension {
    enable() {
        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE_XML, this);
        this._dbus.export(Gio.DBus.session, '/org/sidebay/Positioner');
    }

    disable() {
        if (this._dbus) {
            this._dbus.unexport();
            this._dbus = null;
        }
    }

    _findWindow() {
        const windows = global.display.list_all_windows();
        return windows.find(w => w.get_title() === 'Sidebay' && !w.is_override_redirect()) ?? null;
    }

    MoveWindow(x, y, width, height) {
        const win = this._findWindow();
        if (!win)
            return;
        // user_op=true：程序化移动也走用户操作路径，绕过合成器约束
        win.move_resize_frame(true, x, y, width, height);
    }

    GetWindowInfo() {
        const win = this._findWindow();
        if (!win)
            return [0, 0, 0, 0];
        const rect = win.get_frame_rect();
        return [rect.x, rect.y, rect.width, rect.height];
    }
}
