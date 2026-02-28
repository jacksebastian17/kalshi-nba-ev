from src.math_utils import (
    american_to_decimal,
    decimal_to_implied_prob,
    devig_two_way,
    kalshi_edge_yes,
    kalshi_edge_no,
    kalshi_fee_taker,
    kalshi_fee_maker,
    kalshi_edge_after_fees_yes,
    kalshi_edge_after_fees_no,
    ceil_to_cent,
)


def test_american_positive():
    assert abs(american_to_decimal(150) - 2.5) < 1e-9


def test_american_negative():
    assert abs(american_to_decimal(-110) - (1 + 100/110)) < 1e-9


def test_decimal_to_prob():
    assert abs(decimal_to_implied_prob(2.0) - 0.5) < 1e-9


def test_devig_even_market():
    p_yes, p_no = devig_two_way(1.91, 1.91)
    assert abs(p_yes - 0.5) < 1e-6
    assert abs(p_no - 0.5) < 1e-6
    assert abs((p_yes + p_no) - 1.0) < 1e-9


def test_kalshi_edge_yes():
    assert abs(kalshi_edge_yes(0.57, 0.52) - 0.05) < 1e-9


def test_kalshi_edge_no():
    assert abs(kalshi_edge_no(0.57, 0.40) - 0.03) < 1e-9


# ════════════════════════════════════════════════════════════════════════════
# NEW TESTS: Kalshi Fee Schedule (Official 2026 Formula)
# ════════════════════════════════════════════════════════════════════════════
# Fee formula: ceil_to_cent(0.07 * contracts * P * (1 - P)) for taker
#              ceil_to_cent(0.0175 * contracts * P * (1 - P)) for maker
# Fees peak at P=0.50 (max $0.02 for taker, $0.01 for maker)
# Fees are symmetric: fee(0.20) ≈ fee(0.80)


def test_ceil_to_cent():
    """Test rounding to nearest cent."""
    assert ceil_to_cent(0.0) == 0.0
    assert ceil_to_cent(0.001) == 0.01
    assert ceil_to_cent(0.009) == 0.01
    assert ceil_to_cent(0.010) == 0.01
    assert ceil_to_cent(0.011) == 0.02
    assert ceil_to_cent(0.0251) == 0.03
    assert ceil_to_cent(0.02) == 0.02


def test_kalshi_fee_taker_at_0_05():
    """Test taker fee at 5¢ (cheap contract)."""
    # fee = ceil(0.07 * 1 * 0.05 * 0.95) = ceil(0.003325) = $0.01
    fee = kalshi_fee_taker(0.05)
    assert fee == 0.01, f"Expected $0.01 but got ${fee:.2f}"


def test_kalshi_fee_taker_at_0_50():
    """Test taker fee at 50¢ (peak variance)."""
    # fee = ceil(0.07 * 1 * 0.50 * 0.50) = ceil(0.0175) = $0.02
    fee = kalshi_fee_taker(0.50)
    assert fee == 0.02, f"Expected $0.02 but got ${fee:.2f}"


def test_kalshi_fee_taker_at_0_95():
    """Test taker fee at 95¢ (expensive contract)."""
    # fee = ceil(0.07 * 1 * 0.95 * 0.05) = ceil(0.003325) = $0.01
    fee = kalshi_fee_taker(0.95)
    assert fee == 0.01, f"Expected $0.01 but got ${fee:.2f}"


def test_kalshi_fee_taker_at_0_30():
    """Test taker fee at 30¢ (near-cheap)."""
    # fee = ceil(0.07 * 1 * 0.30 * 0.70) = ceil(0.0147) = $0.02
    fee = kalshi_fee_taker(0.30)
    assert fee == 0.02, f"Expected $0.02 but got ${fee:.2f}"


def test_kalshi_fee_taker_at_0_70():
    """Test taker fee at 70¢ (near-expensive)."""
    # fee = ceil(0.07 * 1 * 0.70 * 0.30) = ceil(0.0147) = $0.02
    fee = kalshi_fee_taker(0.70)
    assert fee == 0.02, f"Expected $0.02 but got ${fee:.2f}"


def test_kalshi_fee_taker_symmetry():
    """Test that fees are symmetric around 0.50."""
    fee_0_20 = kalshi_fee_taker(0.20)
    fee_0_80 = kalshi_fee_taker(0.80)
    assert fee_0_20 == fee_0_80, f"Fees should be symmetric: fee(0.20)=${fee_0_20:.2f} vs fee(0.80)=${fee_0_80:.2f}"


def test_kalshi_fee_maker_at_0_05():
    """Test maker fee at 5¢."""
    # fee = ceil(0.0175 * 1 * 0.05 * 0.95) = ceil(0.00083125) = $0.01
    fee = kalshi_fee_maker(0.05)
    assert fee == 0.01, f"Expected $0.01 but got ${fee:.2f}"


def test_kalshi_fee_maker_at_0_50():
    """Test maker fee at 50¢ (peak)."""
    # fee = ceil(0.0175 * 1 * 0.50 * 0.50) = ceil(0.004375) = $0.01
    fee = kalshi_fee_maker(0.50)
    assert fee == 0.01, f"Expected $0.01 but got ${fee:.2f}"


def test_kalshi_fee_maker_at_0_95():
    """Test maker fee at 95¢."""
    # fee = ceil(0.0175 * 1 * 0.95 * 0.05) = ceil(0.00083125) = $0.01
    fee = kalshi_fee_maker(0.95)
    assert fee == 0.01, f"Expected $0.01 but got ${fee:.2f}"


def test_kalshi_edge_after_fees_yes_at_0_50():
    """Test BUY_YES net edge at 50¢ with good edge."""
    # p_true=60%, ask=50%, raw_edge=10%
    # fee = $0.02
    # net_edge = 10% - 2% = 8%
    net_edge = kalshi_edge_after_fees_yes(0.60, 0.50)
    expected = 0.10 - 0.02
    assert abs(net_edge - expected) < 0.001, f"Expected {expected:.3f} but got {net_edge:.3f}"


def test_kalshi_edge_after_fees_yes_at_0_05():
    """Test BUY_YES net edge at 5¢."""
    # p_true=30%, ask=5%, raw_edge=25%
    # fee = $0.01
    # net_edge = 25% - 1% = 24%
    net_edge = kalshi_edge_after_fees_yes(0.30, 0.05)
    expected = 0.25 - 0.01
    assert abs(net_edge - expected) < 0.001, f"Expected {expected:.3f} but got {net_edge:.3f}"


def test_kalshi_edge_after_fees_yes_at_0_95():
    """Test BUY_YES net edge at 95¢."""
    # p_true=98%, ask=95%, raw_edge=3%
    # fee = $0.01
    # net_edge = 3% - 1% = 2%
    net_edge = kalshi_edge_after_fees_yes(0.98, 0.95)
    expected = 0.03 - 0.01
    assert abs(net_edge - expected) < 0.001, f"Expected {expected:.3f} but got {net_edge:.3f}"


def test_kalshi_edge_after_fees_no_at_0_50():
    """Test BUY_NO net edge at 50¢ with good edge."""
    # p_true_yes=40%, so p_no=60%, ask_no=50%, raw_edge=10%
    # fee = $0.02
    # net_edge = 10% - 2% = 8%
    net_edge = kalshi_edge_after_fees_no(0.40, 0.50)
    expected = 0.10 - 0.02
    assert abs(net_edge - expected) < 0.001, f"Expected {expected:.3f} but got {net_edge:.3f}"


def test_kalshi_edge_after_fees_no_at_0_05():
    """Test BUY_NO net edge at 5¢."""
    # p_true_yes=70%, so p_no=30%, ask_no=5%, raw_edge=25%
    # fee = $0.01
    # net_edge = 25% - 1% = 24%
    net_edge = kalshi_edge_after_fees_no(0.70, 0.05)
    expected = 0.25 - 0.01
    assert abs(net_edge - expected) < 0.001, f"Expected {expected:.3f} but got {net_edge:.3f}"


def test_kalshi_edge_after_fees_no_at_0_95():
    """Test BUY_NO net edge at 95¢."""
    # p_true_yes=2%, so p_no=98%, ask_no=95%, raw_edge=3%
    # fee = $0.01
    # net_edge = 3% - 1% = 2%
    net_edge = kalshi_edge_after_fees_no(0.02, 0.95)
    expected = 0.03 - 0.01
    assert abs(net_edge - expected) < 0.001, f"Expected {expected:.3f} but got {net_edge:.3f}"