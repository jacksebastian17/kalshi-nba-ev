"""
Live micro-betting mode: realistic execution validation for $1-$2 bets.

Prevents fake edges from:
- Stale odds (age > max_odds_age_s)
- Illiquid orderbooks (qty < min_top_qty)  
- Insufficient edge (net_edge < min_net_edge AFTER fees)
- Games too far away (time to start < min_minutes_to_start)

Logs surfaced opportunities to CSV for CLV tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveModeConfig:
    """Configuration for live micro-betting mode."""
    enabled: bool = False
    max_odds_age_s: int = 60  # Skip if Pinnacle odds > 60s old
    min_top_qty: int = 10  # Skip if bid/ask qty < 10 contracts
    min_net_edge: float = 0.02  # Skip if net edge < 2% (for $1-$2 bets)
    min_minutes_to_start: int = 30  # Skip if game starts < 30 min away


def validate_odds_age(
    odds_fetched_at: datetime,
    max_age_s: int,
) -> tuple[bool, Optional[str]]:
    """
    Check if odds are fresh (not stale).
    
    Returns: (is_valid, reason_if_invalid)
    """
    now = datetime.now(timezone.utc)
    age_s = (now - odds_fetched_at).total_seconds()
    
    if age_s > max_age_s:
        return False, f"Pinnacle odds stale: {age_s:.0f}s > {max_age_s}s"
    
    return True, None


def validate_liquidity(
    ask_top_qty: Optional[int],
    min_qty: int,
    side: str,
) -> tuple[bool, Optional[str]]:
    """
    Check if there's enough liquidity at the ask level.
    
    Returns: (is_valid, reason_if_invalid)
    """
    if ask_top_qty is None:
        return False, f"No {side} liquidity data"
    
    if ask_top_qty < min_qty:
        return False, f"{side} top qty {ask_top_qty} < {min_qty}"
    
    return True, None


def validate_net_edge(
    net_edge: float,
    min_edge: float,
) -> tuple[bool, Optional[str]]:
    """
    Check if net edge (after fees + slippage) meets minimum.
    
    Returns: (is_valid, reason_if_invalid)
    """
    if net_edge < min_edge:
        return False, f"Net edge {net_edge:.4f} < min {min_edge:.4f}"
    
    return True, None


def validate_time_to_start(
    game_start_time: datetime,
    min_minutes: int,
) -> tuple[bool, Optional[str]]:
    """
    Check if there's enough time before game starts.
    
    Returns: (is_valid, reason_if_invalid)
    """
    now = datetime.now(timezone.utc)
    minutes_remaining = (game_start_time - now).total_seconds() / 60
    
    if minutes_remaining < min_minutes:
        return False, f"Game starts in {minutes_remaining:.0f}m < {min_minutes}m"
    
    return True, None


def validate_live_mode(
    config: LiveModeConfig,
    odds_fetched_at: datetime,
    kalshi_fetched_at: datetime,
    ask_top_qty: Optional[int],
    net_edge: float,
    game_start_time: datetime,
) -> tuple[bool, Optional[str]]:
    """
    Comprehensive live mode validation.
    
    Returns: (is_valid, reason_if_invalid)
    """
    if not config.enabled:
        # No validation needed if not in live mode
        return True, None
    
    # Check 1: Odds freshness
    valid, reason = validate_odds_age(odds_fetched_at, config.max_odds_age_s)
    if not valid:
        return False, reason
    
    # Check 2: Liquidity
    valid, reason = validate_liquidity(ask_top_qty, config.min_top_qty, "ask")
    if not valid:
        return False, reason
    
    # Check 3: Net edge
    valid, reason = validate_net_edge(net_edge, config.min_net_edge)
    if not valid:
        return False, reason
    
    # Check 4: Time to start
    valid, reason = validate_time_to_start(game_start_time, config.min_minutes_to_start)
    if not valid:
        return False, reason
    
    return True, None
