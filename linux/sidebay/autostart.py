"""开机自启：写入/删除 ~/.config/autostart/sidebay.desktop。"""

import os
from pathlib import Path

DESKTOP_NAME = "sidebay.desktop"


def autostart_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "autostart"


def autostart_content(exec_line: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Sidebay\n"
        "Comment=Dynamic modular sidebar\n"
        f"Exec={exec_line}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def set_autostart(enabled: bool, exec_line: str) -> None:
    path = autostart_dir() / DESKTOP_NAME
    if not enabled:
        try:
            path.unlink()
        except OSError:
            pass
        return
    autostart_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(autostart_content(exec_line))
