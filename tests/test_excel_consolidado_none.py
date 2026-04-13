from Src.infrastructure.exporters.excel_consolidado import _money_fmt, _vol_fmt


def test_money_fmt_none_returns_zero():
    assert _money_fmt(None) == "R$ 0,00"


def test_vol_fmt_none_returns_zero():
    assert _vol_fmt(None) == "0,00"
