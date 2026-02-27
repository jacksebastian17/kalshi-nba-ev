def american_to_decimal(american: int) -> float:
    """
    Convert American odds to decimal odds.

    +150 -> 2.50
    -110 -> 1.909090...
    """
    if american == 0:
        raise ValueError("American odds cannot be 0")

    if american > 0:
        return 1.0 + (american / 100.0)
    else:
        return 1.0 + (100.0 / abs(american))


def decimal_to_implied_prob(decimal_odds: float) -> float:
    """
    Convert decimal odds to implied probability.
    2.00 -> 0.5
    """
    if decimal_odds <= 1.0:
        raise ValueError("Decimal odds must be greater than 1.0")

    return 1.0 / decimal_odds


def devig_two_way(dec_yes: float, dec_no: float) -> tuple[float, float]:
    """
    Remove vig from two-outcome market.

    Returns fair probabilities (p_yes, p_no).
    """
    q_yes = decimal_to_implied_prob(dec_yes)
    q_no = decimal_to_implied_prob(dec_no)

    total = q_yes + q_no
    if total <= 0:
        raise ValueError("Invalid probabilities")

    p_yes = q_yes / total
    p_no = q_no / total

    return p_yes, p_no


def kalshi_edge_yes(p_true_yes: float, ask_price_yes: float) -> float:
    """
    Edge per share (ignoring fees):
    EV = p_true - price
    """
    return p_true_yes - ask_price_yes


def kalshi_edge_no(p_true_yes: float, ask_price_no: float) -> float:
    """
    Edge per share when buying NO:
    EV = (1 - p_true) - price_no
    """
    return (1.0 - p_true_yes) - ask_price_no