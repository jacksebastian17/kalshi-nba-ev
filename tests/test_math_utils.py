from src.math_utils import (
    american_to_decimal,
    decimal_to_implied_prob,
    devig_two_way,
    kalshi_edge_yes,
    kalshi_edge_no,
    kalshi_fee,
    kalshi_edge_after_fees,
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


def test_kalshi_fee():
    # Fee on 74c contract: 10% * (1 - 0.74) = 0.026
    assert abs(kalshi_fee(0.74, 0.10) - 0.026) < 1e-9
    # Fee on 27c contract: 10% * (1 - 0.27) = 0.073
    assert abs(kalshi_fee(0.27, 0.10) - 0.073) < 1e-9


def test_kalshi_edge_after_fees():
    # p_true=75%, price=74c, edge=1%
    # fee = 10% * 26c = 2.6c
    # net = 1% - 2.6% = -1.6%
    net_edge = kalshi_edge_after_fees(0.75, 0.74, 0.10)
    assert abs(net_edge - (0.01 - 0.026)) < 1e-9