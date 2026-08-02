from sidebay.modules.keyboard import format_keys


def test_format_keys_full_combo():
    assert format_keys({"Control", "Shift", "Alt", "Super"}, "A") == "⌃ ⌥ ⇧ ⌘ A"


def test_format_keys_partial():
    assert format_keys({"Shift"}, "S") == "⇧ S"
    assert format_keys({"Control", "Super"}, None) == "⌃ ⌘"


def test_format_keys_empty():
    assert format_keys(set(), None) == ""
    assert format_keys(set(), "X") == "X"


def test_format_keys_order_stable():
    # 顺序固定：Control Alt Shift Super
    assert format_keys({"Super", "Shift", "Alt", "Control"}, "1") == "⌃ ⌥ ⇧ ⌘ 1"
