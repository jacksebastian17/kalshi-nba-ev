from src.decision import decide


def test_buy_yes_when_edge_big():
    # p_true 0.60, ask_yes 0.50 => raw edge 0.10 (10%)
    # fee on 50c = ceil(0.07 * 0.50 * 0.50) = $0.02
    # net edge = 10% - 2% - 0.5% = 7.5%
    # Should buy with default 7% threshold
    d = decide(p_true_yes=0.60, ask_yes=0.50, ask_no=0.50, edge_threshold=0.07, slippage_buffer=0.005, fee_maker=False)
    assert d.action == "BUY_YES", f"Expected BUY_YES but got {d.action}: {d.reason}"


def test_buy_no_when_edge_big():
    # p_true_yes 0.40, so p_no 0.60, ask_no 0.50 => edge 0.10
    # fee on 50c = $0.02, net = 10% - 2% - 0.5% = 7.5%
    d = decide(p_true_yes=0.40, ask_yes=0.50, ask_no=0.50, edge_threshold=0.07, slippage_buffer=0.005, fee_maker=False)
    assert d.action == "BUY_NO", f"Expected BUY_NO but got {d.action}: {d.reason}"


def test_skip_when_edge_small():
    # Small edge should skip
    # p_true 0.51, ask_yes 0.50 => raw edge 0.01 (1%)
    # fee on 50c = $0.02
    # net edge = 1% - 2% - 0.5% = -1.5%
    d = decide(p_true_yes=0.51, ask_yes=0.50, ask_no=0.50, edge_threshold=0.07, slippage_buffer=0.005, fee_maker=False)
    assert d.action == "SKIP", f"Expected SKIP but got {d.action}"


def test_cheap_market_with_good_edge():
    """Test that we CAN now trade cheap markets with good edges."""
    # p_true 0.30, ask_yes 0.05 => raw edge 0.25 (25%)
    # fee on 5c = $0.01
    # net edge = 25% - 1% - 0.5% = 23.5% ✓
    # min_price=0.05 should allow this
    d = decide(p_true_yes=0.30, ask_yes=0.05, ask_no=0.95, edge_threshold=0.07, slippage_buffer=0.005, fee_maker=False, min_price=0.05)
    assert d.action == "BUY_YES", f"Expected BUY_YES on cheap market but got {d.action}: {d.reason}"


def test_expensive_market_with_modest_edge():
    """Test expensive market with modest edge."""
    # p_true 0.80, ask_yes 0.75 => raw edge 0.05 (5%)
    # fee on 75c = ceil(0.07 * 0.75 * 0.25) = ceil(0.013125) = $0.02
    # net edge = 5% - 2% - 0.5% = 2.5% (below 7% threshold)
    d = decide(p_true_yes=0.80, ask_yes=0.75, ask_no=0.25, edge_threshold=0.07, slippage_buffer=0.005, fee_maker=False)
    assert d.action == "SKIP", f"Expected SKIP but got {d.action}: {d.reason}"


def test_maker_fee_lower_than_taker():
    """Test that maker fees are lower than taker fees."""
    # Same market, but using maker vs taker
    # p_true 0.60, ask_yes 0.50 => raw edge 0.10 (10%)
    # taker fee on 50c = $0.02
    # maker fee on 50c = ceil(0.0175 * 0.50 * 0.50) = ceil(0.004375) = $0.01
    # taker: net = 10% - 2% - 0.5% = 7.5%
    # maker: net = 10% - 1% - 0.5% = 8.5%
    
    d_taker = decide(p_true_yes=0.60, ask_yes=0.50, ask_no=0.50, edge_threshold=0.07, slippage_buffer=0.005, fee_maker=False)
    d_maker = decide(p_true_yes=0.60, ask_yes=0.50, ask_no=0.50, edge_threshold=0.07, slippage_buffer=0.005, fee_maker=True)
    
    assert d_taker.action == "BUY_YES"
    assert d_maker.action == "BUY_YES"
    # Maker edge should be better (lower fees)
    assert d_maker.edge > d_taker.edge, f"Maker ({d_maker.edge:.3f}) should have better edge than taker ({d_taker.edge:.3f})"


def test_skip_when_price_filtered():
    """Test that prices below min_price are filtered."""
    d = decide(p_true_yes=0.50, ask_yes=0.02, ask_no=0.98, edge_threshold=0.01, slippage_buffer=0.0, fee_maker=False, min_price=0.05)
    assert d.action == "SKIP", f"Expected SKIP when both prices < min_price but got {d.action}: {d.reason}"