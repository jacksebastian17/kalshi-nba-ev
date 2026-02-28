from __future__ import annotations

import logging
from typing import Optional

from src.kalshi_public import get_orderbook_top
from src.decision import decide, Decision

logger = logging.getLogger(__name__)


def evaluate_market(
    ticker: str,
    p_true_yes: float,
    key_id: Optional[str] = None,
    key_file_path: Optional[str] = None,
    edge_threshold: float = 0.07,
    slippage_buffer: float = 0.005,
    fee_maker: bool = False,
    min_price: float = 0.05,
) -> Decision:
    """High-level helper for V3 (updated fee structure).

    Pulls top prices for *ticker* and runs the decision logic with corrected Kalshi fees.
    
    Args:
        ticker: Kalshi market ticker
        p_true_yes: True probability of YES outcome (from de-vigged odds)
        edge_threshold: Minimum net edge required (default 7%)
        fee_maker: If True, use maker fee; if False, use taker fee (default)
        min_price: Minimum contract price to consider (default 5¢; v2 used 70¢)
    """
    logger.info(f"Evaluating {ticker}")
    logger.debug(f"p_true_yes={p_true_yes:.4f}")
    
    top = get_orderbook_top(ticker, key_id=key_id, key_file_path=key_file_path)
    decision = decide(
        p_true_yes=p_true_yes,
        ask_yes=top.ask_yes,
        ask_no=top.ask_no,
        edge_threshold=edge_threshold,
        slippage_buffer=slippage_buffer,
        fee_maker=fee_maker,
        min_price=min_price,
    )
    logger.info(f"Result: {decision.action}")
    return decision
