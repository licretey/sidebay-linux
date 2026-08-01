"""自选股模块：腾讯行情 qt.gtimg.cn，GB18030 解码。"""

import urllib.request
from dataclasses import dataclass
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module

STOCK_URL = "https://qt.gtimg.cn/q={symbol}&t={ts}"


@dataclass
class StockQuote:
    name: str
    price: str
    change_pct: str
    is_up: bool


def format_stock_symbol(raw: str) -> str:
    clean = raw.lower().strip()
    digits = "".join(c for c in clean if c.isdigit())
    if len(digits) == 6:
        if digits.startswith("6"):
            return "sh" + digits
        if digits.startswith(("0", "3")):
            return "sz" + digits
        if digits.startswith(("4", "8")):
            return "bj" + digits
    return clean


def parse_stock_response(data: bytes) -> StockQuote | None:
    try:
        text = data.decode("gb18030")
    except UnicodeDecodeError:
        return None
    if "~" not in text:
        return None
    parts = text.split("~")
    if len(parts) <= 32:
        return None
    try:
        diff = float(parts[31])
    except ValueError:
        return None
    return StockQuote(
        name=parts[1], price=parts[3],
        change_pct=f"{parts[32]}%",
        is_up=diff >= 0,
    )


class StockModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self.symbol = ""
        for m in store.modules:
            if m.module_id == module_id:
                self.symbol = m.custom_data or "sh000001"
        self._lang = store.settings.language
        self._timer: int | None = None
        self._name: Gtk.Label | None = None
        self._price: Gtk.Label | None = None
        self._change: Gtk.Label | None = None
        self._editing = False

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._name = self._make_label(t("Loading...", self._lang), "sb-module-title")
        self._price = self._make_label("--", "sb-tick-label", size=18)
        self._change = self._make_label("", "sb-tick-label")
        box.append(self._name)
        box.append(self._price)
        box.append(self._change)

        self._entry = Gtk.Entry()
        self._entry.connect("activate", self._on_submit)
        self._entry.set_visible(False)
        box.append(self._entry)

        gesture = Gtk.GestureClick(button=1)
        gesture.set_button(1)
        gesture.connect("pressed", self._on_click)
        box.add_controller(gesture)

        self._timer = GLib.timeout_add(10_000, self._poll)
        self._poll()
        return self._boxed(box)

    def _make_label(self, text: str, css: str, size: int | None = None) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.add_css_class(css)
        if size:
            label.set_markup(f'<span font_size="{size * 1000}">{text}</span>')
        return label

    def _on_click(self, _gesture, _n, x, y) -> None:
        if self._editing:
            return
        self._editing = True
        self._entry.set_text(self.symbol)
        self._entry.set_visible(True)
        self._name.set_visible(False)
        self._entry.grab_focus()

    def _on_submit(self, _entry) -> None:
        formatted = format_stock_symbol(self._entry.get_text())
        self.symbol = formatted if formatted else "sh000001"
        self.store.set_custom_data(self.module_id, self.symbol)
        self._editing = False
        self._entry.set_visible(False)
        self._name.set_visible(True)
        self._poll()

    def _apply_quote(self, quote: StockQuote) -> None:
        """更新行情文本与涨跌色（GTK 4 无 override_color，走 CSS 类，可单测）。"""
        self._name.set_text(quote.name)
        self._price.set_text(quote.price)
        self._change.set_text(quote.change_pct)
        cls = "sb-stock-up" if quote.is_up else "sb-stock-down"
        for label in (self._price, self._change):
            label.remove_css_class("sb-stock-up")
            label.remove_css_class("sb-stock-down")
            label.add_css_class(cls)

    def _poll(self) -> bool:
        symbol, lang = self.symbol, self._lang
        url = STOCK_URL.format(symbol=symbol, ts=int(datetime.now().timestamp()))
        req = urllib.request.Request(url, headers={"User-Agent": "Sidebay/1.0"})

        def _fetch():
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return parse_stock_response(resp.read())
            except OSError:
                return None

        def _done(quote: StockQuote | None) -> None:
            if self._editing or quote is None:
                return
            self._apply_quote(quote)

        import threading
        threading.Thread(target=lambda: GLib.idle_add(_done, _fetch()), daemon=True).start()
        return True

    def on_destroy(self) -> None:
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
