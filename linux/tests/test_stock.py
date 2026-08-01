from sidebay.modules.stock import StockQuote, format_stock_symbol, parse_stock_response


def test_format_symbol_6_digits():
    assert format_stock_symbol("600000") == "sh600000"
    assert format_stock_symbol("000001") == "sz000001"
    assert format_stock_symbol("300750") == "sz300750"
    assert format_stock_symbol("830799") == "bj830799"


def test_format_symbol_passthrough():
    assert format_stock_symbol("AAPL") == "aapl"
    assert format_stock_symbol("  SH600000 ") == "sh600000"


def test_parse_stock_response():
    # v_sh600000="1~浦发银行~600000~10.50~...~+2.5~..."  共 33+ 段
    parts = ["v_sh600000=1", "浦发银行", "600000", "10.50", "10.24", "10.76", "10.20",
             "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
             "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23",
             "0.26", "+2.54", "0"]
    data = ("v_sh600000=\"" + "~".join(parts) + "\";").encode("gb18030")
    quote = parse_stock_response(data)
    assert quote is not None
    assert quote.name == "浦发银行"
    assert quote.price == "10.50"
    assert quote.change_pct == "+2.54%"
    assert quote.is_up


def test_parse_stock_response_invalid():
    assert parse_stock_response(b"not a quote") is None
    assert parse_stock_response("".encode("gb18030")) is None
