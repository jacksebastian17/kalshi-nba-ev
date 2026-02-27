from src.decision import decide


def test_buy_yes_when_edge_big():
    # p_true 0.57, ask_yes 0.52 => raw edge 0.05
    d = decide(p_true_yes=0.57, ask_yes=0.52, ask_no=0.48, edge_threshold=0.02, slippage_buffer=0.0)
    assert d.action == "BUY_YES"


def test_buy_no_when_edge_big():
    # p_true 0.40 => p_no 0.60, ask_no 0.55 => edge 0.05
    d = decide(p_true_yes=0.40, ask_yes=0.62, ask_no=0.55, edge_threshold=0.02, slippage_buffer=0.0)
    assert d.action == "BUY_NO"


def test_skip_when_edge_small():
    d = decide(p_true_yes=0.51, ask_yes=0.50, ask_no=0.50, edge_threshold=0.02, slippage_buffer=0.0)
    assert d.action == "SKIP"