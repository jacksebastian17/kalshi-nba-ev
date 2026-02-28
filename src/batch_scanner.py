"""
Batch scanner for Kalshi markets.

Fetches a list of markets (optionally filtered) and evaluates each one
against a provided sharp probability or model.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.kalshi_public import get_orderbook_top, list_markets
from src.decision import decide, Decision
from src.sharp_model import TwoWayOdds, fair_prob_from_two_way

logger = logging.getLogger(__name__)


def scan_markets(
    search_filter: Optional[str] = None,
    key_id: Optional[str] = None,
    key_file_path: Optional[str] = None,
    p_true_yes: Optional[float] = None,
    amer_yes: Optional[int] = None,
    amer_no: Optional[int] = None,
    edge_threshold: float = 0.07,
    slippage_buffer: float = 0.005,
    fee_maker: bool = False,
    min_price: float = 0.05,
    tickers: Optional[list[str]] = None,
) -> list[dict]:
    """
    Scan a batch of markets and evaluate each one using V3 (updated fees).
    
    Returns a list of results: {ticker, decision, bid_yes, bid_no, ask_yes, ask_no, edge, p_true}.
    
    You must provide either:
      - p_true_yes directly, OR
      - amer_yes + amer_no to de-vig
    
    You must provide one of:
      - search_filter (to list markets from API, requires /markets endpoint access), OR
      - tickers (explicit list to evaluate)
    """
    logger.info(f"Scanning markets (filter: {search_filter or 'none'}, explicit tickers: {len(tickers) if tickers else 0})")
    
    # Get the market list
    if tickers:
        markets = [{"ticker": t} for t in tickers]
        logger.info(f"Using {len(markets)} explicit tickers")
    elif search_filter:
        try:
            markets = list_markets(
                key_id=key_id,
                key_file_path=key_file_path,
                search_filter=search_filter,
            )
        except Exception as e:
            logger.error(f"Failed to list markets: {e}")
            logger.info("Falling back to empty market list. Use --tickers if you want to scan specific markets.")
            markets = []
    else:
        logger.error("Must provide either --filter or --tickers")
        return []
    
    if not markets:
        logger.warning("No markets to evaluate")
        return []
    
    logger.info(f"Found {len(markets)} markets to evaluate")
    
    # Compute fair probability if not provided
    if p_true_yes is None:
        if amer_yes is not None and amer_no is not None:
            logger.info(f"De-vigging American odds: YES={amer_yes}, NO={amer_no}")
            p_true_yes = fair_prob_from_two_way(
                TwoWayOdds(amer_yes=amer_yes, amer_no=amer_no)
            )
            logger.info(f"Fair probability: {p_true_yes:.4f}")
        else:
            raise ValueError(
                "Must provide either p_true_yes or (amer_yes, amer_no)"
            )
    
    # Evaluate each market
    results = []
    for i, market in enumerate(markets, 1):
        ticker = market.get("ticker", "UNKNOWN")
        logger.info(f"[{i}/{len(markets)}] Evaluating {ticker}...")
        
        try:
            top = get_orderbook_top(ticker, key_id=key_id, key_file_path=key_file_path)
            
            # Skip if no prices
            if top.ask_yes is None and top.ask_no is None:
                logger.warning(f"  → No prices available, skipping")
                continue
            
            # Run decision logic
            decision = decide(
                p_true_yes=p_true_yes,
                ask_yes=top.ask_yes,
                ask_no=top.ask_no,
                edge_threshold=edge_threshold,
                slippage_buffer=slippage_buffer,
                fee_maker=fee_maker,
                min_price=min_price,
            )
            
            result = {
                "ticker": ticker,
                "action": decision.action,
                "edge": decision.edge,
                "reason": decision.reason,
                "bid_yes": top.bid_yes,
                "bid_no": top.bid_no,
                "ask_yes": top.ask_yes,
                "ask_no": top.ask_no,
                "p_true_yes": p_true_yes,
            }
            results.append(result)
            
            if decision.action != "SKIP":
                logger.info(f"  ✓ {decision.action} (edge={decision.edge:.4f})")
            else:
                logger.debug(f"  - SKIP (edge={decision.edge:.4f})")
        
        except Exception as e:
            logger.error(f"  ✗ Error evaluating {ticker}: {e}")
            continue
    
    logger.info(f"Completed scan: {len(results)} markets evaluated")
    
    # Summary
    buy_yes_count = sum(1 for r in results if r["action"] == "BUY_YES")
    buy_no_count = sum(1 for r in results if r["action"] == "BUY_NO")
    
    if buy_yes_count > 0 or buy_no_count > 0:
        logger.info(f"------ SUMMARY ------")
        logger.info(f"BUY_YES opportunities: {buy_yes_count}")
        logger.info(f"BUY_NO opportunities: {buy_no_count}")
    
    return results
