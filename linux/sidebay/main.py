"""Sidebay Linux 入口：python3 -m sidebay"""

import sys

from sidebay.app import SidebayApplication


def main() -> int:
    app = SidebayApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
