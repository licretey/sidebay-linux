from pathlib import Path

from sidebay.autostart import autostart_content, autostart_dir, set_autostart


def test_autostart_content_contains_exec(monkeypatch, tmp_path):
    monkeypatch.setattr("sidebay.autostart.autostart_dir", lambda: tmp_path)
    content = autostart_content("flatpak run org.sidebay.SideBay")
    assert "Exec=flatpak run org.sidebay.SideBay" in content
    assert "Name=Sidebay" in content
    assert content.startswith("[Desktop Entry]")


def test_set_autostart_writes_and_removes(monkeypatch, tmp_path):
    monkeypatch.setattr("sidebay.autostart.autostart_dir", lambda: tmp_path)
    set_autostart(True, "python3 -m sidebay")
    assert (tmp_path / "sidebay.desktop").exists()
    set_autostart(False, "python3 -m sidebay")
    assert not (tmp_path / "sidebay.desktop").exists()
