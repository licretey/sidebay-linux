"""Sidebay Linux 入口：python3 -m sidebay"""

import ctypes
import os
import sys


def _set_process_name(name: str = "sidebay") -> None:
    """进程名改为 sidebay 开头（prctl PR_SET_NAME=15，限 15 字符），
    便于 ps/top/脚本识别；argv[0] 同步修改以影响 cmdline 显示。"""
    try:
        libc = ctypes.CDLL(None)
        libc.prctl(15, ctypes.c_char_p(name.encode()[:15]), 0, 0, 0)
    except Exception:
        pass
    try:
        sys.argv[0] = name
    except Exception:
        pass


from sidebay.app import SidebayApplication


def main() -> int:
    _set_process_name("sidebay")
    # 注：GSK_RENDERER=cairo 在 GTK 4.16+ 已移除（无效回退 GL/ngl）；
    # gl 与 ngl 实测内存一致（RSS ~91MB 基线），保留默认即可。
    # Wayland 协议禁止客户端定位窗口（位置设置/贴边失效），且键盘监视
    # 仅 X11 可用。会话为 Wayland 时**强制**走 XWayland（GDK_BACKEND=x11）：
    # XWayland 客户端可经 XMoveResizeWindow 自定位（Mutter 会处理）。
    # 不尊重外部预设的 GDK_BACKEND（如 shell 配置里的 wayland），
    # 否则定位/贴边/键盘功能全部失效。
    if "WAYLAND_DISPLAY" in os.environ:
        os.environ["GDK_BACKEND"] = "x11"
    app = SidebayApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
