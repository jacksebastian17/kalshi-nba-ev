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
    edge_threshold: float = 0.02,
    slippage_buffer: float = 0.005,
) -> Decision:
    """High‑level helper for V1.

    Pulls top prices for *ticker* and runs the decision logic. It doesn't
    attempt to infer which sportsbook line corresponds to the market; the
    caller must supply *p_true_yes* (e.g. from :func:`sharp_model.fair_prob_from_two_way`).

    This function exists mainly to wire components together and to make
    testing of the polling loop easier once we add one.
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
    )
    logger.info(f"Result: {decision.action}")
    return decision
