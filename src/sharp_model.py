from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.math_utils import american_to_decimal, devig_two_way


@dataclass(frozen=True)
class TwoWayOdds:
    """
    Represents a 2-outcome market for the SAME line (e.g., spread -3.5 both sides).
    Provide either american or decimal odds (decimal preferred if you already have it).
    """
    dec_yes: Optional[float] = None
    dec_no: Optional[float] = None
    amer_yes: Optional[int] = None
    amer_no: Optional[int] = None


def fair_prob_from_two_way(odds: TwoWayOdds) -> float:
    """
    Returns p_true_yes (fair probability of YES) after de-vig.
    """
    if odds.dec_yes is not None and odds.dec_no is not None:
        dec_yes = odds.dec_yes
        dec_no = odds.dec_no
    elif odds.amer_yes is not None and odds.amer_no is not None:
        dec_yes = american_to_decimal(odds.amer_yes)
        dec_no = american_to_decimal(odds.amer_no)
    else:
        raise ValueError("Provide either (dec_yes, dec_no) or (amer_yes, amer_no)")

    p_yes, _ = devig_two_way(dec_yes, dec_no)
    return p_yes