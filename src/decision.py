from __future__ import annotations
from dataclasses import dataclass

from src.math_utils import kalshi_edge_yes, kalshi_edge_no, kalshi_fee_taker, kalshi_fee_maker


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
    fee_maker: bool = False,  # If True, use maker fee; else use taker fee
    min_price: float = 0.05,  # Minimum price filter (adjusted based on fee curve peak)
) -> Decision:
    """
    V3 decision rule with corrected Kalshi fee structure.
    
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
    
    5. SUBTRACT: Kalshi fees (CORRECTED)
       - Taker fee: ceil_to_cent(0.07 * contracts * P * (1 - P))
       - Peaks at P=0.50 (max $0.02 per contract), not at extremes
       - This reward high-variance markets, not just expensive ones
    
    6. FILTER: Consider prices >= 5¢ (adjustable based on fee curve)
       - Old model (fees peak at 0%): required >= 70¢ filter
       - New model (fees peak at 50¢): fees are SYMMETRIC
       - Fee at 5¢: ~$0.01, Fee at 95¢: ~$0.01 (same!)
       - Can now trade cheaper markets with good edges
    
    7. APPLY: Minimum edge threshold
       - Need raw edge of 7-10% after all costs
       - Raw edge - Fee ($0.01-$0.02) - Slippage (0.5%) >= 7%
    
    ════════════════════════════════════════════════════════════════════════════
    WHEN YOU'D PROFIT (EXAMPLES WITH NEW FEES):
    ════════════════════════════════════════════════════════════════════════════
    
    Example 1: Cheap market with decent edge
    "You think Portland has 30% chance, Kalshi prices YES at 20¢ (20% chance)"
    
    - True probability: 30% (p_yes)
    - Kalshi YES ask: 20¢
    - Raw edge: 30% - 20% = 10%
    - Fee: ceil(0.07 * 1 * 0.20 * 0.80) = ceil(0.0112) = $0.02
    - Slippage: 0.5%
    - Net edge: 10% - 2% - 0.5% = 7.5% ✓ Profitable!
    
    Example 2: Expensive market with good edge
    "You think Charlotte has 80% chance, Kalshi prices YES at 74¢ (74% chance)"
    
    - True probability: 80% (p_yes)
    - Kalshi YES ask: 74¢
    - Raw edge: 80% - 74% = 6%
    - Fee: ceil(0.07 * 1 * 0.74 * 0.26) = ceil(0.01348) = $0.02
    - Slippage: 0.5%
    - Net edge: 6% - 2% - 0.5% = 3.5% ❌ Below threshold (needs 7%)
    
    ════════════════════════════════════════════════════════════════════════════
    NEW INSIGHT: Fee symmetry
    ════════════════════════════════════════════════════════════════════════════
    
    The new fee formula is symmetric around P=0.5:
    - fee(0.20) ≈ fee(0.80) [both ~$0.01]
    - fee(0.30) ≈ fee(0.70) [both ~$0.02]
    - fee(0.50) = $0.02 (peak)
    
    This means opportunities can exist at ANY price, not just extremes:
    - Cheap underdogs: good if true prob is much higher
    - Expensive favorites: good if true prob is slightly higher
    
    ════════════════════════════════════════════════════════════════════════════
    
    Args:
        p_true_yes: True probability of YES outcome (from de-vigged Pinnacle odds)
        ask_yes: Market ask price for YES on Kalshi
        ask_no: Market ask price for NO on Kalshi
        edge_threshold: Minimum net edge required (default 7%)
        slippage_buffer: Safety margin for spread/execution costs (default 0.5%)
        fee_maker: If True, use maker fee (lower); if False, use taker fee (default)
        min_price: Minimum contract price to trade (default 5¢; old system used 70¢)
    
    Returns:
        Decision with action (BUY_YES/BUY_NO/SKIP), edge metrics, and reasoning
    """
    candidates: list[tuple[str, float, float, float]] = []  # (action, net_edge, raw_edge, fee)

    # Select fee function based on order type
    fee_fn = kalshi_fee_maker if fee_maker else kalshi_fee_taker

    # Evaluate YES side if it passes the price filter
    if ask_yes is not None and ask_yes >= min_price:
        raw_edge_yes = kalshi_edge_yes(p_true_yes, ask_yes)
        fee_yes = fee_fn(ask_yes)
        # Net edge = raw edge - fee - slippage
        net_edge_yes = raw_edge_yes - fee_yes - slippage_buffer
        candidates.append(("BUY_YES", net_edge_yes, raw_edge_yes, fee_yes))

    # Evaluate NO side if it passes the price filter
    if ask_no is not None and ask_no >= min_price:
        raw_edge_no = kalshi_edge_no(p_true_yes, ask_no)
        fee_no = fee_fn(ask_no)
        net_edge_no = raw_edge_no - fee_no - slippage_buffer
        candidates.append(("BUY_NO", net_edge_no, raw_edge_no, fee_no))

    # If no candidates pass the price filter, we can't trade
    if not candidates:
        return Decision(
            action="SKIP",
            edge=0.0,
            raw_edge=0.0,
            fee=0.0,
            reason=f"No prices available >= {min_price:.0%} or no markets exist"
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
            reason=f"Net edge {best_edge:.1%} exceeds {edge_threshold:.0%} threshold (raw: {best_raw_edge:.1%}, fee: {best_fee:.3f})"
        )
    
    # Otherwise skip the opportunity
    return Decision(
        action="SKIP",
        edge=best_edge,
        raw_edge=best_raw_edge,
        fee=best_fee,
        reason=f"Net edge {best_edge:.1%} below {edge_threshold:.0%} threshold (raw: {best_raw_edge:.1%}, fee: {best_fee:.3f})"
    )