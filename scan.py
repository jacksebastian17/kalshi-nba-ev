#!/usr/bin/env python3
"""
Clean output scanner for Pinnacle → Kalshi +EV detection.

Supports live micro-betting mode for realistic execution validation.
Configure LiveModeConfig directly in code below.

Run: python scan.py

Output: game-by-game results, optionally logged to CSV.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from src.decision import decide
from src.game_matcher import build_kxnbagame_tickers
from src.kalshi_public import get_orderbook_top, get_market_details
from src.math_utils import kalshi_edge_yes, kalshi_edge_no
from src.odds_api import get_nba_games_with_pinnacle, get_odds_api_keys_from_env
from src.sharp_model import TwoWayOdds, fair_prob_from_two_way
from src.live_mode import LiveModeConfig, validate_live_mode

load_dotenv()

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Edit these values directly
# ════════════════════════════════════════════════════════════════════════════
LIVE_MODE = False  # Set to True to enable live micro-betting validation
MAX_ODDS_AGE_S = 60  # Skip if Pinnacle odds > 60 seconds old
MIN_TOP_QTY = 10  # Skip if Kalshi bid/ask qty < 10 contracts
MIN_NET_EDGE = 0.02  # Skip if net edge < 2% (for $1-$2 validation bets)
MIN_MINUTES_TO_START = 30  # Skip if game starts < 30 minutes away

# Configure logging for clean terminal output
# Set to DEBUG to see detailed API info, INFO for game filtering, WARNING for errors only
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
# Keep most loggers at INFO, but suppress verbose debug noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def parse_game_start_time(commence_time_str: str) -> datetime:
    """Parse ISO 8601 commence_time to UTC datetime."""
    if commence_time_str.endswith("Z"):
        commence_time_str = commence_time_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(commence_time_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def has_game_started(game_start_time: datetime) -> bool:
    """Check if a game has already started."""
    now = datetime.now(timezone.utc)
    return now >= game_start_time


def main():
    """Scan and print clean game-by-game results."""
    live_config = LiveModeConfig(
        enabled=LIVE_MODE,
        max_odds_age_s=MAX_ODDS_AGE_S,
        min_top_qty=MIN_TOP_QTY,
        min_net_edge=MIN_NET_EDGE,
        min_minutes_to_start=MIN_MINUTES_TO_START,
    )
    
    if live_config.enabled:
        mode_str = f"LIVE MODE (age<{MAX_ODDS_AGE_S}s, qty>={MIN_TOP_QTY}, edge>{MIN_NET_EDGE:.1%}, time>={MIN_MINUTES_TO_START}m)"
    else:
        mode_str = "STANDARD MODE"
    
    print("\n" + "=" * 120)
    print(f"NBA +EV SCAN | {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | {mode_str}")
    print("=" * 120 + "\n")
    
    odds_api_keys = get_odds_api_keys_from_env()
    if not odds_api_keys:
        print("✗ ERROR: ODDS_API_KEY or ODDS_API_KEYS not found in .env")
        return 1
    
    key_id = os.getenv("KALSHI_KEY_ID")
    key_file = os.getenv("KALSHI_KEY_FILE")
    
    try:
        pinnacle_games = get_nba_games_with_pinnacle(odds_api_keys)
    except Exception as e:
        print(f"✗ Failed to fetch Pinnacle games: {e}")
        return 1
    
    if not pinnacle_games:
        print("No NBA games with Pinnacle odds found.")
        print("=" * 120)
        return 0
    
    opportunity_count = 0
    
    for game in pinnacle_games:
        tickers = build_kxnbagame_tickers(game)
        if not tickers:
            continue
        
        # Parse game start time
        game_start_time = parse_game_start_time(game.commence_time)
        
        # Skip if game has already started (to avoid live games with fast-moving odds)
        if has_game_started(game_start_time):
            logger.info(f"Skipping {game.away_team} @ {game.home_team} - game already started")
            continue
        
        try:
            # Fetch market details to check status
            away_market = get_market_details(tickers.away_yes, key_id=key_id, key_file_path=key_file)
            away_status = away_market.get("status", "unknown")
            logger.debug(f"Away market {tickers.away_yes} status: {away_status}")
            
            home_market = get_market_details(tickers.home_yes, key_id=key_id, key_file_path=key_file)
            home_status = home_market.get("status", "unknown")
            logger.debug(f"Home market {tickers.home_yes} status: {home_status}")
            
            # Skip if either market is live/closed/resolved (allow "open", "active", or "unknown")
            BLOCKED_STATUSES = {"live", "closed", "resolved", "paused"}
            if away_status in BLOCKED_STATUSES:
                logger.info(f"Skipping {game.away_team} - market status is {away_status}")
                continue
            if home_status in BLOCKED_STATUSES:
                logger.info(f"Skipping {game.home_team} - market status is {home_status}")
                continue
            
            away_ob = get_orderbook_top(tickers.away_yes, key_id=key_id, key_file_path=key_file)
            home_ob = get_orderbook_top(tickers.home_yes, key_id=key_id, key_file_path=key_file)
            kalshi_fetched_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.warning(f"Failed to fetch Kalshi data for {game.away_team} @ {game.home_team}: {e}")
            continue
        
        p_away = fair_prob_from_two_way(
            TwoWayOdds(amer_yes=game.pinnacle_away_ml, amer_no=game.pinnacle_home_ml)
        )
        p_home = 1.0 - p_away
        
        # Calculate edges for both YES and NO sides
        away_edge_yes = kalshi_edge_yes(p_away, away_ob.ask_yes) if away_ob.ask_yes else None
        away_edge_no = kalshi_edge_no(p_away, away_ob.ask_no) if away_ob.ask_no else None
        home_edge_yes = kalshi_edge_yes(p_home, home_ob.ask_yes) if home_ob.ask_yes else None
        home_edge_no = kalshi_edge_no(p_home, home_ob.ask_no) if home_ob.ask_no else None
        
        away_decision = decide(
            p_true_yes=p_away,
            ask_yes=away_ob.ask_yes,
            ask_no=away_ob.ask_no,
            edge_threshold=0.07,  # 7% minimum edge
            fee_maker=False,  # Use taker fees
            min_price=0.05  # Lower min price with new fee structure
        )
        home_decision = decide(
            p_true_yes=p_home,
            ask_yes=home_ob.ask_yes,
            ask_no=home_ob.ask_no,
            edge_threshold=0.07,
            fee_maker=False,
            min_price=0.05
        )
        
        # Live mode validation (if enabled)
        away_yes_live_valid = True
        away_yes_live_reason = None
        away_no_live_valid = True
        away_no_live_reason = None
        home_yes_live_valid = True
        home_yes_live_reason = None
        home_no_live_valid = True
        home_no_live_reason = None
        
        if live_config.enabled and away_decision.action == "BUY_YES":
            away_yes_live_valid, away_yes_live_reason = validate_live_mode(
                live_config,
                game.odds_fetched_at,
                kalshi_fetched_at,
                away_ob.ask_yes_qty if hasattr(away_ob, 'ask_yes_qty') else None,
                away_decision.edge,
                game_start_time,
            )
        
        if live_config.enabled and away_decision.action == "BUY_NO":
            away_no_live_valid, away_no_live_reason = validate_live_mode(
                live_config,
                game.odds_fetched_at,
                kalshi_fetched_at,
                away_ob.ask_no_qty if hasattr(away_ob, 'ask_no_qty') else None,
                away_decision.edge,
                game_start_time,
            )
        
        if live_config.enabled and home_decision.action == "BUY_YES":
            home_yes_live_valid, home_yes_live_reason = validate_live_mode(
                live_config,
                game.odds_fetched_at,
                kalshi_fetched_at,
                home_ob.ask_yes_qty if hasattr(home_ob, 'ask_yes_qty') else None,
                home_decision.edge,
                game_start_time,
            )
        
        if live_config.enabled and home_decision.action == "BUY_NO":
            home_no_live_valid, home_no_live_reason = validate_live_mode(
                live_config,
                game.odds_fetched_at,
                kalshi_fetched_at,
                home_ob.ask_no_qty if hasattr(home_ob, 'ask_no_qty') else None,
                home_decision.edge,
                game_start_time,
            )
        
        # Format prices to 2 decimals
        away_ask_yes = f"{away_ob.ask_yes:.2f}" if away_ob.ask_yes else "N/A"
        away_ask_no = f"{away_ob.ask_no:.2f}" if away_ob.ask_no else "N/A"
        home_ask_yes = f"{home_ob.ask_yes:.2f}" if home_ob.ask_yes else "N/A"
        home_ask_no = f"{home_ob.ask_no:.2f}" if home_ob.ask_no else "N/A"
        
        away_edge_yes_str = f"{away_edge_yes:+.3f}" if away_edge_yes else "N/A"
        away_edge_no_str = f"{away_edge_no:+.3f}" if away_edge_no else "N/A"
        home_edge_yes_str = f"{home_edge_yes:+.3f}" if home_edge_yes else "N/A"
        home_edge_no_str = f"{home_edge_no:+.3f}" if home_edge_no else "N/A"
        
        # Print game header
        print(f"{game.away_team:20} @ {game.home_team:20} | Pinnacle: {game.pinnacle_away_ml:+6d}/{game.pinnacle_home_ml:+6d}")
        
        # Print away side (apply live mode filter if needed)
        away_action = away_decision.action
        if live_config.enabled and away_decision.action == "BUY_YES" and not away_yes_live_valid:
            away_action = "SKIP"
        if live_config.enabled and away_decision.action == "BUY_NO" and not away_no_live_valid:
            away_action = "SKIP"
        
        away_fee_str = f"fee={away_decision.fee:.3f}" if away_decision.fee > 0 else "filtered"
        away_net_str = f"net={away_decision.edge:+.3f}" if away_decision.fee > 0 else "<5c"
        print(f"  {game.away_team:15} | p={p_away:.3f} | Y:{away_ask_yes} N:{away_ask_no} | raw_y={away_edge_yes_str} raw_n={away_edge_no_str} | {away_fee_str} {away_net_str} | {away_action}")
        
        # Print home side (apply live mode filter if needed)
        home_action = home_decision.action
        if live_config.enabled and home_decision.action == "BUY_YES" and not home_yes_live_valid:
            home_action = "SKIP"
        if live_config.enabled and home_decision.action == "BUY_NO" and not home_no_live_valid:
            home_action = "SKIP"
        
        home_fee_str = f"fee={home_decision.fee:.3f}" if home_decision.fee > 0 else "filtered"
        home_net_str = f"net={home_decision.edge:+.3f}" if home_decision.fee > 0 else "<5c"
        print(f"  {game.home_team:15} | p={p_home:.3f} | Y:{home_ask_yes} N:{home_ask_no} | raw_y={home_edge_yes_str} raw_n={home_edge_no_str} | {home_fee_str} {home_net_str} | {home_action}")
        
        # Print details
        if away_decision.action != "SKIP":
            if away_action == "SKIP" and live_config.enabled:
                print(f"    -> {away_decision.reason} (LIVE MODE: {away_yes_live_reason or away_no_live_reason})")
            else:
                print(f"    -> {away_decision.reason}")
        
        if home_decision.action != "SKIP":
            if home_action == "SKIP" and live_config.enabled:
                print(f"    -> {home_decision.reason} (LIVE MODE: {home_yes_live_reason or home_no_live_reason})")
            else:
                print(f"    -> {home_decision.reason}")
        
        # Count opportunities
        if away_decision.action != "SKIP" or home_decision.action != "SKIP":
            opportunity_count += 1
        
        print()
    
    print("=" * 120)
    if opportunity_count > 0:
        print(f"[+] Found {opportunity_count} +EV opportunity(ies)")
    else:
        print("[-] No +EV opportunities found")
    print("=" * 120)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
