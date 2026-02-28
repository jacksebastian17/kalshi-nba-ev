#!/usr/bin/env python3
"""
Clean output scanner for Pinnacle → Kalshi +EV detection.

Run: python scan.py

Output: game-by-game results without logging noise.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from src.decision import decide
from src.game_matcher import build_kxnbagame_tickers
from src.kalshi_public import get_orderbook_top
from src.math_utils import kalshi_edge_yes, kalshi_edge_no
from src.odds_api import get_nba_games_with_pinnacle
from src.sharp_model import TwoWayOdds, fair_prob_from_two_way

load_dotenv()

# Configure logging for clean terminal output
# Set to DEBUG to see detailed API info, WARNING for errors only
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
# Keep all loggers at WARNING for clean output
logging.getLogger().setLevel(logging.WARNING)


def main():
    """Scan and print clean game-by-game results."""
    print("\n" + "=" * 120)
    print(f"NBA +EV SCAN | {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 120 + "\n")
    
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("✗ ERROR: ODDS_API_KEY not found in .env")
        return 1
    
    key_id = os.getenv("KALSHI_KEY_ID")
    key_file = os.getenv("KALSHI_KEY_FILE")
    
    try:
        pinnacle_games = get_nba_games_with_pinnacle(api_key)
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
        
        try:
            away_ob = get_orderbook_top(tickers.away_yes, key_id=key_id, key_file_path=key_file)
            home_ob = get_orderbook_top(tickers.home_yes, key_id=key_id, key_file_path=key_file)
        except Exception:
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
        
        # Print away side with net edge after fees
        away_fee_str = f"fee={away_decision.fee:.3f}" if away_decision.fee > 0 else "filtered"
        away_net_str = f"net={away_decision.edge:+.3f}" if away_decision.fee > 0 else "<70c"
        print(f"  {game.away_team:15} | p={p_away:.3f} | Y:{away_ask_yes} N:{away_ask_no} | raw_y={away_edge_yes_str} raw_n={away_edge_no_str} | {away_fee_str} {away_net_str} | {away_decision.action}")
        
        # Print home side with net edge after fees
        home_fee_str = f"fee={home_decision.fee:.3f}" if home_decision.fee > 0 else "filtered"
        home_net_str = f"net={home_decision.edge:+.3f}" if home_decision.fee > 0 else "<70c"
        print(f"  {game.home_team:15} | p={p_home:.3f} | Y:{home_ask_yes} N:{home_ask_no} | raw_y={home_edge_yes_str} raw_n={home_edge_no_str} | {home_fee_str} {home_net_str} | {home_decision.action}")
        
        # If action was taken, show the reason
        if away_decision.action != "SKIP":
            print(f"    -> {away_decision.reason}")
        if home_decision.action != "SKIP":
            print(f"    -> {home_decision.reason}")
        print()
        
        if away_decision.action != "SKIP" or home_decision.action != "SKIP":
            opportunity_count += 1
    
    print("=" * 120)
    if opportunity_count > 0:
        print(f"[+] Found {opportunity_count} +EV opportunity(ies)")
    else:
        print("[-] No +EV opportunities found")
    print("=" * 120)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
