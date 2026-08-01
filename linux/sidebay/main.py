"""Sidebay Linux 入口：python3 -m sidebay"""

import os
import sys

from sidebay.app import SidebayApplication


def main() -> int:
    # 内存验收：GTK 4 默认 GL 渲染器在无 GPU 环境（Xvfb/llvmpipe）会加载
    # libLLVM + NVIDIA 编译栈，空闲 RSS 约 270MB；cairo 渲染器约 95MB 且视觉一致。
    # 用户可用环境变量 GSK_RENDERER 覆盖。
    os.environ.setdefault("GSK_RENDERER", "cairo")
    app = SidebayApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
