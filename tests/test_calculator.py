from sidebay.modules.calculator import Calculator


def test_initial_display():
    assert Calculator().display == "0"


def test_typing_and_basic_ops():
    calc = Calculator()
    assert calc.press("1") == "1"
    assert calc.press("+") == "1"
    assert calc.press("2") == "2"
    assert calc.press("=") == "3"
    assert calc.press("×") == "3"
    assert calc.press("4") == "4"
    assert calc.press("=") == "12"


def test_divide_by_zero():
    calc = Calculator()
    calc.press("8")
    calc.press("÷")
    calc.press("0")
    assert calc.press("=") == "0"


def test_clear():
    calc = Calculator()
    calc.press("9")
    calc.press("+")
    assert calc.press("C") == "0"


def test_negate_and_percent():
    calc = Calculator()
    calc.press("5")
    assert calc.press("±") == "-5"
    calc.press("C")
    calc.press("2")
    assert calc.press("%") == "0.02"


def test_decimal_point():
    calc = Calculator()
    calc.press("1")
    calc.press(".")
    calc.press("5")
    assert calc.display == "1.5"
    calc.press(".")
    assert calc.display == "1.5"  # 已有点，忽略
