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


def kalshi_fee(price: float, fee_rate: float = 0.10) -> float:
    """
    Calculate Kalshi's fee based on expected profit.
    
    CRITICAL: Kalshi's fee structure is not a flat amount per contract.
    Instead, Kalshi charges a percentage of your POTENTIAL PROFIT.
    
    Fee = fee_rate × (1 - price)
    
    This creates a MASSIVE asymmetry:
    - Buying underdogs (cheap, e.g., 20¢): Fee = 10% × 80¢ = 8¢ (40% of price!)
    - Buying favorites (expensive, e.g., 80¢): Fee = 10% × 20¢ = 2¢ (2.5% of price)
    
    This is why we ONLY trade contracts >= 70¢. Below that, fees destroy any edge.
    
    Args:
        price: Purchase price of the contract (0-1), e.g., 0.74 for 74¢
        fee_rate: Fee tier rate based on monthly volume
                  - 0.10 (10%) for <$25k/month (default)
                  - 0.07 (7%) for $25k-$100k
                  - 0.05 (5%) for $100k-$500k
                  - 0.02 (2%) for $500k+
    
    Returns:
        Fee amount per contract (in dollars)
    
    Examples:
        Charlotte YES at 74¢: fee = 0.10 × (1 - 0.74) = 0.026 = 2.6¢
        Portland NO at 27¢: fee = 0.10 × (1 - 0.27) = 0.073 = 7.3¢ (ouch!)
    """
    expected_profit = 1.0 - price
    return fee_rate * expected_profit


def kalshi_edge_after_fees(p_true: float, ask_price: float, fee_rate: float = 0.10) -> float:
    """
    Calculate NET edge after accounting for Kalshi fees.
    
    This is your ACTUAL profit per share, not the raw edge.
    
    Formula:
      net_edge = raw_edge - fee
              = (p_true - price) - fee_rate × (1 - price)
    
    Example (Charlotte NO at 27¢, true prob 26%):
      raw_edge = 0.26 - 0.27 = -0.01 (negative!)
      fee = 0.10 × (1 - 0.27) = 0.073
      net_edge = -0.01 - 0.073 = -0.083 = -8.3% ❌
    
    This is why we need 7%+ edges - fees take 2-8% depending on price!
    """
    raw_edge = p_true - ask_price
    fee = kalshi_fee(ask_price, fee_rate)
    return raw_edge - fee