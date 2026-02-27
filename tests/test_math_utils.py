from src.math_utils import (
    american_to_decimal,
    decimal_to_implied_prob,
    devig_two_way,
    kalshi_edge_yes,
    kalshi_edge_no,
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