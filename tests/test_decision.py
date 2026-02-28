from src.decision import decide


def test_buy_yes_when_edge_big():
    # p_true 0.80, ask_yes 0.72 => raw edge 0.08 (8%)
    # fee on 72c = 10% * (1-0.72) = 2.8c
    # net edge = 8% - 2.8% - 0.5% = 4.7%
    # Should skip with default 7% threshold, but buy with lower threshold
    d = decide(p_true_yes=0.80, ask_yes=0.72, ask_no=0.28, edge_threshold=0.04, slippage_buffer=0.0, fee_rate=0.10)
    assert d.action == "BUY_YES"


def test_buy_no_when_edge_big():
    # p_true 0.20 => p_no 0.80, ask_no 0.72 => edge 0.08
    # fee on 72c = 2.8c, net = 4.7%
    d = decide(p_true_yes=0.20, ask_yes=0.82, ask_no=0.72, edge_threshold=0.04, slippage_buffer=0.0, fee_rate=0.10)
    assert d.action == "BUY_NO"


def test_skip_when_edge_small():
    # Small edge should skip
    d = decide(p_true_yes=0.51, ask_yes=0.50, ask_no=0.50, edge_threshold=0.07, slippage_buffer=0.0, fee_rate=0.10)
    assert d.action == "SKIP"


def test_skip_when_price_too_low():
    # Even with huge edge, skip if BOTH prices < 70c (unfavorable fees)
    d = decide(p_true_yes=0.50, ask_yes=0.30, ask_no=0.40, edge_threshold=0.01, slippage_buffer=0.0, fee_rate=0.10, min_price=0.70)
    assert d.action == "SKIP"
    assert "70%" in d.reason or "available" in d.reason.lower()