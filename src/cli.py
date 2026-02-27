"""Minimal command-line pilot for the Kalshi NBA EV engine.

This module is not required by the core library; it's provided purely as a
quick way to exercise the components from the terminal.  You can do things
like:

    python -m src.cli --ticker NBA-... --key-id <ID> --key-file <path> --action top
    python -m src.cli --ticker NBA-... --key-id <ID> --key-file <path> \\
      --amer-yes -110 --amer-no -110 --action eval

Environment variables:
    KALSHI_KEY_ID - your Kalshi API key ID
    KALSHI_KEY_FILE - path to your private key PEM file
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from src.kalshi_public import get_orderbook_top
from src.sharp_model import TwoWayOdds, fair_prob_from_two_way
from src.scanner import evaluate_market
from src.batch_scanner import scan_markets
from src.decision import Decision

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kalshi NBA EV pilot scanner",
        epilog="Set KALSHI_KEY_ID and KALSHI_KEY_FILE environment variables or use --key-id/--key-file",
    )
    parser.add_argument("--ticker", required=False, help="Kalshi market ticker (required for --action top/eval)")
    parser.add_argument(
        "--key-id",
        help="Kalshi API key ID (or set KALSHI_KEY_ID env var)",
    )
    parser.add_argument(
        "--key-file",
        help="Path to Kalshi private key PEM file (or set KALSHI_KEY_FILE env var)",
    )
    parser.add_argument(
        "--dec-yes",
        type=float,
        help="decimal odds for YES side (used with --action eval)",
    )
    parser.add_argument(
        "--dec-no",
        type=float,
        help="decimal odds for NO side (used with --action eval)",
    )
    parser.add_argument(
        "--amer-yes",
        type=int,
        help="American odds for YES side (used with --action eval)",
    )
    parser.add_argument(
        "--amer-no",
        type=int,
        help="American odds for NO side (used with --action eval)",
    )
    parser.add_argument(
        "--action",
        choices=["top", "eval", "batch"],
        default="top",
        help="`top` just fetches the book; `eval` also runs the decision logic; `batch` scans multiple markets",
    )
    parser.add_argument(
        "--filter",
        help="Filter markets by ticker substring (used with batch action, e.g. 'kxnbagame' for NBA)",
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated list of specific tickers to scan (e.g. 'KXNBAGAME-1,KXNBAGAME-2')",
    )
    return parser.parse_args(argv)


def compute_p_true(args: argparse.Namespace) -> Optional[float]:
    """Return de‑vigged probability or None if not enough info."""
    if args.dec_yes is not None and args.dec_no is not None:
        return fair_prob_from_two_way(
            TwoWayOdds(dec_yes=args.dec_yes, dec_no=args.dec_no)
        )
    if args.amer_yes is not None and args.amer_no is not None:
        return fair_prob_from_two_way(
            TwoWayOdds(amer_yes=args.amer_yes, amer_no=args.amer_no)
        )
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger.info(f"Starting Kalshi NBA EV scanner")
    logger.info(f"Action: {args.action}")
    
    # Validate ticker is provided for single-market actions
    if args.action in ["top", "eval"] and not args.ticker:
        logger.error(f"--ticker is required for --action {args.action}")
        print(f"error: --ticker is required for --action {args.action}", file=sys.stderr)
        return 1
    
    if args.action == "top":
        logger.info(f"Target market: {args.ticker}")
        logger.info("Fetching top of book...")
        top = get_orderbook_top(args.ticker, key_id=args.key_id, key_file_path=args.key_file)
        logger.info(f"Success! Orderbook: {top}")
        print(top)
        return 0

    if args.action == "eval":
        logger.info(f"Target market: {args.ticker}")
        logger.info("Computing fair probability from supplied odds...")
        p = compute_p_true(args)
        if p is None:
            logger.error("must supply both yes/no odds with --dec- or --amer-")
            print("error: must supply both yes/no odds with --dec- or --amer-", file=sys.stderr)
            return 1

        logger.info(f"Fair probability (de-vigged): {p:.4f}")
        logger.info("Running evaluation...")
        decision: Decision = evaluate_market(args.ticker, p, key_id=args.key_id, key_file_path=args.key_file)
        logger.info(f"Decision: {decision.action} | Edge: {decision.edge:.4f} | Reason: {decision.reason}")
        print(decision)
        return 0

    if args.action == "batch":
        # Batch mode: scan multiple markets
        logger.info("Batch scan mode")
        logger.info(f"Filter: {args.filter or 'none'}")
        
        # Parse explicit tickers if provided
        tickers = None
        if args.tickers:
            tickers = [t.strip() for t in args.tickers.split(",")]
            logger.info(f"Explicit tickers: {tickers}")
        
        p = compute_p_true(args)
        if p is None:
            # Try with American odds args
            if args.amer_yes is not None and args.amer_no is not None:
                logger.info(f"De-vigging: {args.amer_yes} vs {args.amer_no}")
                results = scan_markets(
                    search_filter=args.filter,
                    tickers=tickers,
                    key_id=args.key_id,
                    key_file_path=args.key_file,
                    amer_yes=args.amer_yes,
                    amer_no=args.amer_no,
                )
            else:
                logger.error("must supply both yes/no odds with --dec- or --amer-")
                print("error: must supply both yes/no odds with --dec- or --amer-", file=sys.stderr)
                return 1
        else:
            results = scan_markets(
                search_filter=args.filter,
                tickers=tickers,
                key_id=args.key_id,
                key_file_path=args.key_file,
                p_true_yes=p,
            )
        
        # Print results
        import json
        print("\n" + "="*80)
        print("BATCH SCAN RESULTS")
        print("="*80)
        
        for result in results:
            action = result["action"]
            emoji = "✓" if action != "SKIP" else "-"
            print(f"{emoji} {result['ticker']:30} {action:10} edge={result['edge']:+.4f} "
                  f"ask_yes={result['ask_yes']:.2f} ask_no={result['ask_no']:.2f}")
        
        print("="*80)
        print(f"Total: {len(results)} evaluated")
        return 0

    # Should not reach here
    logger.error(f"Unknown action: {args.action}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
