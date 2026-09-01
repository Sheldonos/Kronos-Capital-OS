from kcos.derivatives.options import OptionAnalytics, OptionQuote, TradeExpressionEngine


def test_option_iv_and_defined_risk_expression():
    price = OptionAnalytics.greeks(100, 100, .25, .03, .30, "CALL")["price"]
    iv = OptionAnalytics.implied_vol(price, 100, 100, .25, .03, "CALL")
    assert abs(iv - .30) < .01
    chain = [
        OptionQuote("c1", "X", 100, .25, "CALL", price-.05, price+.05),
        OptionQuote("p1", "X", 95, .25, "PUT", 2.0, 2.1),
        OptionQuote("c2", "X", 105, .25, "CALL", 2.0, 2.1),
    ]
    surface = OptionAnalytics.surface(chain, 100, .03)
    assert surface["available"]
    proposal = TradeExpressionEngine().propose(.08, .8, .25, surface, 100)
    assert proposal["expression"] in {"LONG_CALL", "CALL_DEBIT_SPREAD"}
    assert proposal["naked_short_options_allowed"] is False
