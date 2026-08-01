from sidebay.i18n import t


def test_known_key_zh():
    assert t("Settings", "zh") == "侧边栏模块管理"


def test_known_key_en():
    assert t("Settings", "en") == "Settings"


def test_missing_key_returns_key():
    assert t("NoSuchKey", "zh") == "NoSuchKey"
