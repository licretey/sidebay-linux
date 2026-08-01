"""4x5 极简计算器：纯逻辑类 + GTK 视图。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from sidebay.modules.base import Module

BUTTONS = [
    ["C", "±", "%", "÷"],
    ["7", "8", "9", "×"],
    ["4", "5", "6", "-"],
    ["1", "2", "3", "+"],
    ["0", ".", "="],
]
OPERATORS = {"÷", "×", "-", "+", "="}
FUNCTIONS = {"C", "±", "%"}


class Calculator:
    def __init__(self):
        self.display = "0"
        self.previous = 0.0
        self.operation: str | None = None
        self.typing_new = True

    def press(self, key: str) -> str:
        if key == "C":
            self.display, self.previous, self.operation, self.typing_new = "0", 0.0, None, True
        elif key == "±":
            current = self._parse()
            self.display = self._format(-current)
        elif key == "%":
            current = self._parse()
            self.display = self._format(current / 100)
        elif key == ".":
            if not self.typing_new and "." not in self.display:
                self.display += "."
            elif self.typing_new:
                self.display, self.typing_new = "0.", False
        elif key in OPERATORS:
            self._calculate(self._parse())
            self.operation = key if key != "=" else None
            self.typing_new = True
        else:
            self.display = key if self.typing_new else self.display + key
            self.typing_new = False
        return self.display

    def _parse(self) -> float:
        try:
            return float(self.display)
        except ValueError:
            return 0.0

    def _calculate(self, current: float) -> None:
        if self.operation is None:
            self.previous = current
            return
        result = self.previous
        if self.operation == "+":
            result += current
        elif self.operation == "-":
            result -= current
        elif self.operation == "×":
            result *= current
        elif self.operation == "÷":
            result = result / current if current != 0 else 0
        self.previous = result
        self.display = self._format(result)

    @staticmethod
    def _format(num: float) -> str:
        if abs(num - round(num)) < 1e-9:
            return f"{num:.0f}"
        return f"{num:.10f}".rstrip("0").rstrip(".")


class CalculatorModule(Module):
    def build(self) -> Gtk.Widget:
        self.calc = Calculator()
        self._buttons: list[Gtk.Button] = []
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._display_label = Gtk.Label(label="0")
        self._display_label.add_css_class("sb-calc-display")
        self._display_label.set_xalign(1.0)
        box.append(self._display_label)

        for row in BUTTONS:
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            for key in row:
                button = Gtk.Button(label=key)
                button.set_hexpand(True)
                button.set_size_request(-1, 22)
                button.connect("clicked", self._on_key, key)
                # 运算符橙、功能键灰、数字玻璃
                if key in OPERATORS:
                    button.add_css_class("sb-calc-op")
                elif key in FUNCTIONS:
                    button.add_css_class("sb-calc-fn")
                else:
                    button.add_css_class("sb-btn-glass")
                self._buttons.append(button)
                row_box.append(button)
            box.append(row_box)
        return self._boxed(box)

    def _on_key(self, _btn: Gtk.Button, key: str) -> None:
        self._display_label.set_text(self.calc.press(key))
