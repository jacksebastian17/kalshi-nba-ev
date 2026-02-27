"""
Match Pinnacle NBA games to Kalshi NBA markets.

This is a utility for testing game matching logic before building the team mapper.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher

from src.decision import decide
from src.kalshi_public import get_orderbook_top, list_markets
from src.odds_api import NBAGame, get_nba_games_with_pinnacle
from src.sharp_model import TwoWayOdds, fair_prob_from_two_way

logger = logging.getLogger(__name__)


TEAM_NAME_TO_ABBREV = {
    "atlanta hawks": "ATL",
    "boston celtics": "BOS",
    "brooklyn nets": "BKN",
    "charlotte hornets": "CHA",
    "chicago bulls": "CHI",
    "cleveland cavaliers": "CLE",
    "dallas mavericks": "DAL",
    "denver nuggets": "DEN",
    "detroit pistons": "DET",
    "golden state warriors": "GSW",
    "houston rockets": "HOU",
    "indiana pacers": "IND",
    "los angeles clippers": "LAC",
    "la clippers": "LAC",
    "los angeles lakers": "LAL",
    "la lakers": "LAL",
    "memphis grizzlies": "MEM",
    "miami heat": "MIA",
    "milwaukee bucks": "MIL",
    "minnesota timberwolves": "MIN",
    "new orleans pelicans": "NOP",
    "new york knicks": "NYK",
    "oklahoma city thunder": "OKC",
    "orlando magic": "ORL",
    "philadelphia 76ers": "PHI",
    "phoenix suns": "PHX",
    "portland trail blazers": "POR",
    "portland trailblazers": "POR",
    "sacramento kings": "SAC",
    "san antonio spurs": "SAS",
    "toronto raptors": "TOR",
    "utah jazz": "UTA",
    "washington wizards": "WAS",
}


def _normalize_team_name(name: str) -> str:
    return " ".join(name.lower().replace(".", "").split())


def team_to_abbrev(team_name: str) -> str | None:
    normalized = _normalize_team_name(team_name)
    abbrev = TEAM_NAME_TO_ABBREV.get(normalized)
    if not abbrev:
        logger.warning(f"Unknown NBA team name: {team_name}")
    return abbrev


def kalshi_date_from_commence(commence_time: str) -> str | None:
    try:
        if commence_time.endswith("Z"):
            commence_time = commence_time.replace("Z", "+00:00")
        dt = datetime.fromisoformat(commence_time)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        try:
            eastern = ZoneInfo("America/New_York")
            dt = dt.astimezone(eastern)
        except Exception:
            # Windows may not have tzdata; fall back to fixed EST offset.
            dt = dt.astimezone(timezone.utc) + timedelta(hours=-5)

        return dt.strftime("%y%b%d").upper()
    except Exception as exc:
        logger.warning(f"Failed to parse commence_time '{commence_time}': {exc}")
        return None


@dataclass(frozen=True)
class KalshiGameTickers:
    event: str
    away_yes: str
    home_yes: str
    date_code: str


def build_kxnbagame_tickers(game: NBAGame) -> KalshiGameTickers | None:
    away_abbrev = team_to_abbrev(game.away_team)
    home_abbrev = team_to_abbrev(game.home_team)
    date_code = kalshi_date_from_commence(game.commence_time)

    if not away_abbrev or not home_abbrev or not date_code:
        return None

    event = f"KXNBAGAME-{date_code}{away_abbrev}{home_abbrev}"
    away_yes = f"{event}-{away_abbrev}"
    home_yes = f"{event}-{home_abbrev}"
    return KalshiGameTickers(event=event, away_yes=away_yes, home_yes=home_yes, date_code=date_code)


def similarity_ratio(a: str, b: str) -> float:
    """
    Calculate how similar two strings are (0.0 to 1.0).
    Higher = more similar.
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def fuzzy_match_team(pinnacle_team: str, kalshi_ticker: str, threshold: float = 0.6) -> bool:
    """
    Check if a Pinnacle team name is likely in a Kalshi ticker.
    
    Examples:
        fuzzy_match_team("Denver Nuggets", "KXNBAGAME-26FEB27DENOKC-OKC")  # True (DEN in DENOKC)
        fuzzy_match_team("Boston Celtics", "KXNBAGAME-26FEB27BOSGSW-GSW")  # True (BOS in BOSGSW)
    """
    # Extract 3-letter team abbreviations (common pattern)
    team_abbrev = pinnacle_team[:3].upper()  # "Denver" -> "DEN"
    
    if team_abbrev in kalshi_ticker.upper():
        return True
    
    # Fallback: fuzzy match team name pieces
    ticker_lower = kalshi_ticker.lower()
    for word in pinnacle_team.lower().split():
        if len(word) >= 3 and similarity_ratio(word, ticker_lower) > threshold:
            return True
    
    return False


def match_game_to_kalshi(
    game: NBAGame, kalshi_ticker: str
) -> bool:
    """
    Check if a Pinnacle game matches a Kalshi market ticker.
    
    Returns True if both away and home teams appear in the ticker.
    """
    away_match = fuzzy_match_team(game.away_team, kalshi_ticker)
    home_match = fuzzy_match_team(game.home_team, kalshi_ticker)
    
    return away_match and home_match


def find_kalshi_match(
    game: NBAGame, kalshi_tickers: list[str]
) -> str | None:
    """
    Find the Kalshi market ticker that matches this Pinnacle game.
    
    Returns the matching ticker, or None if no match found.
    """
    for ticker in kalshi_tickers:
        if match_game_to_kalshi(game, ticker):
            return ticker
    return None


def preview_kalshi_markets(key_id: str | None = None, key_file_path: str | None = None) -> None:
    """
    Preview what markets exist in Kalshi to debug filtering issues.
    Looks specifically for KXNBAGAME markets (game winner markets).
    """
    logger.info("Fetching ALL Kalshi markets (no filter, up to 1000)...")
    
    markets = list_markets(
        search_filter=None,  # No filter, get everything
        key_id=key_id,
        key_file_path=key_file_path,
        limit=1000,  # Fetch up to 1000 to see full scope
    )
    
    print("\n" + "=" * 120)
    print(f"ANALYZING {len(markets)} TOTAL KALSHI MARKETS")
    print("=" * 120)
    
    # Group by prefix
    from collections import defaultdict
    by_prefix = defaultdict(list)
    
    for market in markets:
        ticker = market.get("ticker", "UNKNOWN")
        prefix = ticker.split("-")[0] if ticker else "UNKNOWN"
        by_prefix[prefix].append(market)
    
    # Show all prefixes
    print("\n--- MARKET PREFIXES AVAILABLE ---")
    for prefix in sorted(by_prefix.keys()):
        count = len(by_prefix[prefix])
        print(f"{prefix}: {count} markets")
    
    # Focus on KXNBAGAME
    print("\n--- KXNBAGAME MARKETS (GAME WINNERS) ---")
    nba_game_winners = by_prefix.get("KXNBAGAME", [])
    
    if nba_game_winners:
        print(f"\n✓ Found {len(nba_game_winners)} KXNBAGAME markets!")
        for market in nba_game_winners[:10]:
            ticker = market.get("ticker")
            title = market.get("title", "?")[:100]
            print(f"  {ticker}: {title}")
        if len(nba_game_winners) > 10:
            print(f"  ... and {len(nba_game_winners) - 10} more")
    else:
        print("\n✗ NO KXNBAGAME markets found in API response")
        print("\nPossible reasons:")
        print("  1. NBA markets not live right now")
        print("  2. API pagination cut off before reaching them")
        print("  3. Markets exist but under different formatting")
        
        # Check if there are any NBA-related keywords in other markets
        nba_keywords = ["denver", "okc", "boston", "lakers", "warriors", "nba"]
        nba_related = []
        for market in markets:
            title = market.get("title", "").lower()
            if any(kw in title for kw in nba_keywords):
                nba_related.append(market)
        
        if nba_related:
            print(f"\n  Found {len(nba_related)} markets with NBA keywords:")
            for m in nba_related[:5]:
                prefix = m.get("ticker", "").split("-")[0]
                title = m.get("title", "?")[:80]
                print(f"    {prefix}: {title}")


def direct_match_and_eval(
    api_key: str,
    key_id: str | None = None,
    key_file_path: str | None = None,
) -> None:
    """
    Fetch Pinnacle games, construct KXNBAGAME tickers directly, and evaluate edges.
    """
    logger.info("Fetching Pinnacle games...")
    pinnacle_games = get_nba_games_with_pinnacle(api_key)

    print("\n" + "=" * 140)
    print("PINNACLE → KALSHI DIRECT MATCH + EDGE CHECK")
    print("=" * 140)

    for game in pinnacle_games:
        tickers = build_kxnbagame_tickers(game)
        if not tickers:
            print(
                f"✗ SKIP     {game.away_team:20} @ {game.home_team:20} "
                f"| Pinnacle: {game.pinnacle_away_ml:+6d}/{game.pinnacle_home_ml:+6d} "
                f"| Kalshi: N/A (mapping/date)"
            )
            continue

        try:
            away_ob = get_orderbook_top(tickers.away_yes, key_id=key_id, key_file_path=key_file_path)
            home_ob = get_orderbook_top(tickers.home_yes, key_id=key_id, key_file_path=key_file_path)
        except Exception as exc:
            print(
                f"✗ ERROR    {game.away_team:20} @ {game.home_team:20} "
                f"| Kalshi: {tickers.event} ({exc})"
            )
            continue

        p_away = fair_prob_from_two_way(
            TwoWayOdds(amer_yes=game.pinnacle_away_ml, amer_no=game.pinnacle_home_ml)
        )
        p_home = 1.0 - p_away

        away_decision = decide(p_true_yes=p_away, ask_yes=away_ob.ask_yes, ask_no=away_ob.ask_no)
        home_decision = decide(p_true_yes=p_home, ask_yes=home_ob.ask_yes, ask_no=home_ob.ask_no)

        print(
            f"{game.away_team:20} @ {game.home_team:20} "
            f"| Pinnacle: {game.pinnacle_away_ml:+6d}/{game.pinnacle_home_ml:+6d}"
        )
        print(
            f"  Away ({tickers.away_yes})  p_true={p_away:.3f} "
            f"ask_yes={away_ob.ask_yes} ask_no={away_ob.ask_no} "
            f"=> {away_decision.action} edge={away_decision.edge:.3f}"
        )
        print(
            f"  Home ({tickers.home_yes})  p_true={p_home:.3f} "
            f"ask_yes={home_ob.ask_yes} ask_no={home_ob.ask_no} "
            f"=> {home_decision.action} edge={home_decision.edge:.3f}"
        )

    print("=" * 140)


if __name__ == "__main__":
    import os
    import sys
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("ERROR: ODDS_API_KEY not found in .env")
        sys.exit(1)
    
    key_id = os.getenv("KALSHI_KEY_ID")
    key_file = os.getenv("KALSHI_KEY_FILE")
    
    # Direct matching without relying on /markets listing.
    direct_match_and_eval(api_key, key_id, key_file)
