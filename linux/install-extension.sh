#!/usr/bin/env bash
# 安装并启用 Sidebay 定位扩展（GNOME 45+，ESM 格式）
#
# 作用：GNOME Wayland 下允许 Sidebay 窗口任意 X/Y 定位（含垂直移动）。
# 不安装时功能降级：X 坐标可移动，Y 固定顶部（Xorg 会话下不受影响）。
set -e
cd "$(dirname "$0")"

EXT_DIR="gnome-extension/org.sidebay.Positioner"
UUID="org.sidebay.Positioner"

if ! command -v gnome-extensions >/dev/null 2>&1; then
    echo "错误：未找到 gnome-extensions 命令（需在 GNOME 会话内运行）" >&2
    exit 1
fi

# gnome-extensions install 接受目录（GNOME 45+）或 zip
if gnome-extensions install --force "$EXT_DIR" 2>/dev/null; then
    :
else
    # 兼容旧版本：打包 zip 安装
    tmpzip="/tmp/${UUID}.zip"
    rm -f "$tmpzip"
    (cd "$EXT_DIR" && zip -qr "$tmpzip" .)
    gnome-extensions install --force "$tmpzip"
fi

gnome-extensions enable "$UUID" 2>/dev/null || true

echo "已安装并启用 ${UUID}"
echo "提示：若未立即生效，请重启 GNOME Shell（Alt+F2 → r）或重新登录。"
