import pytest
from src.sharp_model import TwoWayOdds, fair_prob_from_two_way


def test_fair_prob_from_decimal_even():
    odds = TwoWayOdds(dec_yes=1.91, dec_no=1.91)
    p = fair_prob_from_two_way(odds)
    assert abs(p - 0.5) < 1e-6


def test_fair_prob_from_american_even():
    odds = TwoWayOdds(amer_yes=-110, amer_no=-110)
    p = fair_prob_from_two_way(odds)
    assert abs(p - 0.5) < 1e-6


def test_missing_inputs_raises():
    with pytest.raises(ValueError):
        fair_prob_from_two_way(TwoWayOdds(dec_yes=1.9))