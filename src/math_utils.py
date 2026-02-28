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


def ceil_to_cent(value: float) -> float:
    """
    Round a dollar amount UP to the nearest $0.01 (cent).
    
    Used for Kalshi fee calculations to ensure we never underestimate fees.
    
    Args:
        value: Dollar amount (e.g., 0.0251 for 2.51¢)
    
    Returns:
        Value rounded up to nearest cent (e.g., 0.03 for 3¢)
    
    Examples:
        ceil_to_cent(0.0251) = 0.03
        ceil_to_cent(0.02) = 0.02
        ceil_to_cent(0.02001) = 0.03
    """
    import math
    return math.ceil(value * 100) / 100


def kalshi_fee_taker(price: float, contracts: int = 1) -> float:
    """
    Calculate Kalshi's TAKER fee (actual fee charged when you submit a market order).
    
    Official formula: ceil_to_cent(0.07 * contracts * P * (1 - P))
    
    The fee is based on a quadratic curve that peaks at P=0.5, which represents
    the maximum variance of the contract. This is more fair than older models.
    
    Args:
        price: Purchase price of the contract in dollars (0-1), e.g., 0.74 for 74¢
        contracts: Number of contracts (default 1)
    
    Returns:
        Fee per contract in dollars, rounded up to nearest cent
    
    Examples:
        price=0.05 (5¢):   fee = ceil(0.07 * 1 * 0.05 * 0.95) = ceil(0.003325) = $0.01
        price=0.50 (50¢):  fee = ceil(0.07 * 1 * 0.50 * 0.50) = ceil(0.0175) = $0.02
        price=0.95 (95¢):  fee = ceil(0.07 * 1 * 0.95 * 0.05) = ceil(0.003325) = $0.01
    """
    gross_fee = 0.07 * contracts * price * (1.0 - price)
    return ceil_to_cent(gross_fee)


def kalshi_fee_maker(price: float, contracts: int = 1) -> float:
    """
    Calculate Kalshi's MAKER fee (rebate/charge for providing liquidity).
    
    Official formula: ceil_to_cent(0.0175 * contracts * P * (1 - P))
    
    Maker fees are lower (1.75% vs 7% taker) as an incentive for the market maker
    to provide liquidity.
    
    Args:
        price: Sell price of the contract in dollars (0-1), e.g., 0.74 for 74¢
        contracts: Number of contracts (default 1)
    
    Returns:
        Fee per contract in dollars, rounded up to nearest cent
    
    Examples:
        price=0.05 (5¢):   fee = ceil(0.0175 * 1 * 0.05 * 0.95) = ceil(0.00083125) = $0.01
        price=0.50 (50¢):  fee = ceil(0.0175 * 1 * 0.50 * 0.50) = ceil(0.004375) = $0.01
        price=0.95 (95¢):  fee = ceil(0.0175 * 1 * 0.95 * 0.05) = ceil(0.00083125) = $0.01
    """
    gross_fee = 0.0175 * contracts * price * (1.0 - price)
    return ceil_to_cent(gross_fee)


def kalshi_edge_after_fees_yes(p_true_yes: float, ask_price_yes: float, contracts: int = 1) -> float:
    """
    Calculate NET edge for BUY_YES position after accounting for Kalshi taker fees.
    
    Formula:
      net_edge = (p_true - price) - fee - slippage_buffer
    
    Note: slippage_buffer is typically applied separately by the decision engine.
    
    Args:
        p_true_yes: True probability of YES outcome
        ask_price_yes: Market ask price for YES contract
        contracts: Number of contracts (default 1)
    
    Returns:
        Net edge after fees (as decimal, e.g., 0.05 for 5%)
    
    Example (price=50¢, p_true=60%):
      raw_edge = 0.60 - 0.50 = 0.10 (10%)
      fee = ceil(0.07 * 1 * 0.50 * 0.50) = $0.02 (2%)
      net_edge = 0.10 - 0.02 = 0.08 (8%) ✓
    """
    raw_edge = p_true_yes - ask_price_yes
    fee = kalshi_fee_taker(ask_price_yes, contracts)
    return raw_edge - fee


def kalshi_edge_after_fees_no(p_true_yes: float, ask_price_no: float, contracts: int = 1) -> float:
    """
    Calculate NET edge for BUY_NO position after accounting for Kalshi taker fees.
    
    Formula:
      net_edge = ((1 - p_true) - price) - fee - slippage_buffer
    
    Note: slippage_buffer is typically applied separately by the decision engine.
    
    Args:
        p_true_yes: True probability of YES outcome (so 1 - p_true_yes = prob of NO)
        ask_price_no: Market ask price for NO contract
        contracts: Number of contracts (default 1)
    
    Returns:
        Net edge after fees (as decimal, e.g., 0.05 for 5%)
    
    Example (price=50¢, p_true=40%, so p_false=60%):
      raw_edge = (1 - 0.40) - 0.50 = 0.10 (10%)
      fee = ceil(0.07 * 1 * 0.50 * 0.50) = $0.02 (2%)
      net_edge = 0.10 - 0.02 = 0.08 (8%) ✓
    """
    raw_edge = (1.0 - p_true_yes) - ask_price_no
    fee = kalshi_fee_taker(ask_price_no, contracts)
    return raw_edge - fee