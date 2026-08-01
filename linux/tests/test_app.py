"""app 层单测：autostart Exec 行按运行方式计算（M1）。"""

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")

from sidebay.app import autostart_exec_line  # noqa: E402


def test_autostart_exec_line_flatpak(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "org.sidebay.SideBay")
    assert autostart_exec_line() == "flatpak run org.sidebay.SideBay"


def test_autostart_exec_line_host_uses_run_sh(monkeypatch):
    from pathlib import Path

    monkeypatch.delenv("FLATPAK_ID", raising=False)
    line = autostart_exec_line()
    # 直接运行分支必须是仓库 linux/run.sh 的绝对路径（真实存在的文件）
    assert line.endswith("/linux/run.sh")
    assert Path(line).is_file()
