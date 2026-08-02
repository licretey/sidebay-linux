"""Sidebay Linux 入口：python3 -m sidebay"""

import os
import sys

from sidebay.app import SidebayApplication


def main() -> int:
    # 内存验收：GTK 4 默认 GL 渲染器在无 GPU 环境（Xvfb/llvmpipe）会加载
    # libLLVM + NVIDIA 编译栈，空闲 RSS 约 270MB；cairo 渲染器约 95MB 且视觉一致。
    # 用户可用环境变量 GSK_RENDERER 覆盖。
    os.environ.setdefault("GSK_RENDERER", "cairo")
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
