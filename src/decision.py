from __future__ import annotations
from dataclasses import dataclass

from src.math_utils import kalshi_edge_yes, kalshi_edge_no, kalshi_fee


@dataclass(frozen=True)
class Decision:
    action: str  # "BUY_YES", "BUY_NO", "SKIP"
    edge: float  # best edge per share (after fees and slippage)
    raw_edge: float  # edge before fees/slippage
    fee: float  # fee amount per contract
    reason: str


def decide(
    p_true_yes: float,
    ask_yes: float | None,
    ask_no: float | None,
    edge_threshold: float = 0.07,  # Increased to 7% (was 2%)
    slippage_buffer: float = 0.005,
    fee_rate: float = 0.10,  # 10% fee rate (default tier)
    min_price: float = 0.70,  # Only trade contracts >= 70¢
) -> Decision:
    """
    V2 decision rule with fee awareness.
    
    ════════════════════════════════════════════════════════════════════════════
    THE STRATEGY:
    ════════════════════════════════════════════════════════════════════════════
    
    1. COMPARE: Pinnacle (sharp) vs Kalshi (retail)
       - Pinnacle is the sharpest sportsbook (2-3% vig, accepts sharp bettors)
       - Kalshi is a retail prediction market (less efficient)
       - If they disagree, there's a potential edge
    
    2. CALCULATE: True probability from Pinnacle
       - De-vig the odds to get fair probability (example: 26% for Portland)
       - This is your "ground truth"
    
    3. FETCH: Kalshi market prices
       - See what retail traders think (example: 28% for Portland)
       - If higher than Pinnacle → contract is OVERPRICED
       - If lower than Pinnacle → contract is UNDERPRICED (potential edge)
    
    4. COMPUTE: Raw edge
       - edge = |p_true - market_price|
       - Example: 26% (Pinnacle) vs 28% (Kalshi) = -2% edge (overpriced)
                  26% (Pinnacle) vs 25% (Kalshi) = +1% edge (underpriced!)
    
    5. SUBTRACT: Kalshi fees
       - Fee = 10% × (1 - price)
       - HUGE asymmetry: cheap contracts (20¢) have 8¢ fee, expensive (80¢) have 2¢
       - This destroys underdogs even if they're underpriced
    
    6. FILTER: Only consider prices >= 70¢
       - Below 70¢: fees are > 3% (kills any small edge)
       - At 70¢: fee = 10% × 30¢ = 3% (breakeven with small edges)
       - At 80¢: fee = 10% × 20¢ = 2% (favorable)
    
    7. APPLY: Minimum edge threshold
       - Need raw edge of 7-10% after all costs
       - Raw edge - Fee (2-3%) - Slippage (0.5%) >= 7%
       - Means raw edge needs to be ~10% minimum
    
    ════════════════════════════════════════════════════════════════════════════
    WHEN YOU'D PROFIT:
    ════════════════════════════════════════════════════════════════════════════
    
    "You think Portland has 30% chance (Pinnacle says 26%)"
    Kalshi inexplicably prices it at 20¢ (20% chance) after news breaks
    
    - True probability: 30% (your model via Pinnacle + news)
    - Kalshi price: 20¢
    - Raw edge: 30% - 20% = 10%
    - Fee: 10% × (1 - 0.20) = 8%
    - Slippage: 0.5%
    - Net edge: 10% - 8% - 0.5% = 1.5% ❌ Still negative!
    
    You'd actually need the price to drop to 15¢ to profit:
    - Raw edge: 30% - 15% = 15%
    - Fee: 10% × (1 - 0.15) = 8.5%
    - Net edge: 15% - 8.5% - 0.5% = 6% ✓ Profitable!
    
    But 15¢ is filtered out because < 70¢...
    
    This is why real opportunities are RARE:
    - Need 20%+ mispricings on expensive markets (70¢+)
    - Or find inefficient market segments (player props, illiquid markets)
    
    ════════════════════════════════════════════════════════════════════════════
    
    Args:
        p_true_yes: True probability of YES outcome (from de-vigged Pinnacle odds)
        ask_yes: Market ask price for YES on Kalshi
        ask_no: Market ask price for NO on Kalshi
        edge_threshold: Minimum net edge required (default 7%)
        slippage_buffer: Safety margin for spread/execution costs (default 0.5%)
        fee_rate: Kalshi fee tier (10% for typical trader, 2% for high volume)
        min_price: Minimum contract price to trade (default 70¢ for fee efficiency)
    
    Returns:
        Decision with action (BUY_YES/BUY_NO/SKIP), edge metrics, and reasoning
    """
    candidates: list[tuple[str, float, float, float]] = []  # (action, net_edge, raw_edge, fee)

    # Evaluate YES side if it passes the price filter
    if ask_yes is not None and ask_yes >= min_price:
        raw_edge_yes = kalshi_edge_yes(p_true_yes, ask_yes)
        fee_yes = kalshi_fee(ask_yes, fee_rate)
        # Net edge = what you'd actually profit after all costs
        net_edge_yes = raw_edge_yes - fee_yes - slippage_buffer
        candidates.append(("BUY_YES", net_edge_yes, raw_edge_yes, fee_yes))

    # Evaluate NO side if it passes the price filter
    if ask_no is not None and ask_no >= min_price:
        raw_edge_no = kalshi_edge_no(p_true_yes, ask_no)
        fee_no = kalshi_fee(ask_no, fee_rate)
        net_edge_no = raw_edge_no - fee_no - slippage_buffer
        candidates.append(("BUY_NO", net_edge_no, raw_edge_no, fee_no))

    # If no candidates pass the price filter, we can't trade
    if not candidates:
        return Decision(
            action="SKIP",
            edge=0.0,
            raw_edge=0.0,
            fee=0.0,
            reason=f"No prices available >= {min_price:.0%} (too expensive to trade)"
        )

    # Take the best candidate (highest net edge)
    best_action, best_edge, best_raw_edge, best_fee = max(candidates, key=lambda x: x[1])

    # Only execute if net edge exceeds threshold
    if best_edge >= edge_threshold:
        return Decision(
            action=best_action,
            edge=best_edge,
            raw_edge=best_raw_edge,
            fee=best_fee,
            reason=f"Net edge {best_edge:.1%} exceeds {edge_threshold:.0%} threshold (raw: {best_raw_edge:.1%}, fee: {best_fee:.1%})"
        )
    
    # Otherwise skip the opportunity
    return Decision(
        action="SKIP",
        edge=best_edge,
        raw_edge=best_raw_edge,
        fee=best_fee,
        reason=f"Net edge {best_edge:.1%} below {edge_threshold:.0%} threshold (raw: {best_raw_edge:.1%}, fee: {best_fee:.1%})"
    )