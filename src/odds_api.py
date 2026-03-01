"""
Odds API integration for fetching Pinnacle NBA moneylines.

The Odds API provides real-time odds from multiple sportsbooks.
We'll use it to fetch Pinnacle moneylines (the sharpest market).

Docs: https://the-odds-api.com/
"""

from __future__ import annotations

import logging
import httpx
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Odds API endpoint
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


def get_odds_api_keys_from_env() -> list[str]:
    """
    Resolve Odds API keys from environment.

    Priority:
    1) ODDS_API_KEYS (comma-separated list)
    2) ODDS_API_KEY (single key)
    """
    import os

    multi = os.getenv("ODDS_API_KEYS", "").strip()
    if multi:
        keys = [key.strip() for key in multi.split(",") if key.strip()]
        if keys:
            return keys

    single = os.getenv("ODDS_API_KEY", "").strip()
    return [single] if single else []


def _parse_iso8601_to_utc(iso_string: str) -> datetime:
    """
    Parse ISO 8601 timestamp string to UTC datetime.
    
    Handles both timezone-aware and naive ISO strings.
    """
    # Try parsing with fromisoformat first (Python 3.7+)
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        # Convert to UTC naive if timezone-aware
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError):
        # Fallback for older Python or malformed strings
        logger.warning(f"Could not parse ISO 8601: {iso_string}, using UTC now")
        return datetime.utcnow()


@dataclass(frozen=True)
class NBAGame:
    """Represents a matchup from Odds API."""
    id: str
    away_team: str
    home_team: str
    commence_time: str  # ISO 8601 timestamp (preserved for logging)
    pinnacle_away_ml: Optional[int]  # American odds
    pinnacle_home_ml: Optional[int]  # American odds
    game_start_time: datetime = field(default_factory=datetime.utcnow)  # Parsed datetime (UTC)
    odds_fetched_at: datetime = field(default_factory=datetime.utcnow)  # When we fetched the odds


def _fetch_nba_odds_data(api_key: str) -> list[dict]:
    """Fetch raw NBA odds response using a single key."""
    logger.debug("Fetching NBA games from Odds API with Pinnacle odds...")

    url = f"{ODDS_API_BASE}/sports/basketball_nba/odds"
    params = {
        "apiKey": api_key,
        "markets": "h2h",  # Moneyline only
        "bookmakers": "pinnacle",  # Only Pinnacle (sharpest)
        "oddsFormat": "american",
    }

    response = httpx.get(url, params=params, timeout=10.0)
    response.raise_for_status()

    remaining = response.headers.get("x-requests-remaining", "?")
    used = response.headers.get("x-requests-used", "?")
    logger.debug(f"Odds API key suffix ...{api_key[-4:]} used={used}, remaining={remaining}")

    data = response.json()
    logger.debug(f"Fetched {len(data)} games from Odds API")
    return data


def get_nba_games_with_pinnacle(api_key: str | list[str]) -> list[NBAGame]:
    """
    Fetch all NBA games with Pinnacle moneylines from The Odds API.
    
    Args:
        api_key: One key or list of keys (for rotation/fallback)
    
    Returns:
        List of NBAGame objects with Pinnacle moneylines
    
    Raises:
        httpx.HTTPError if API request fails
        ValueError if response is malformed
    """
    keys = [api_key] if isinstance(api_key, str) else [key for key in api_key if key]
    if not keys:
        raise ValueError("No Odds API keys provided")

    data: list[dict] | None = None
    last_error: Exception | None = None

    for idx, key in enumerate(keys, start=1):
        try:
            logger.debug(f"Trying Odds API key {idx}/{len(keys)} (suffix ...{key[-4:]})")
            data = _fetch_nba_odds_data(key)
            break
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code if e.response else None
            last_error = e
            logger.warning(
                f"Odds API key {idx}/{len(keys)} failed with status {status_code}; trying next key"
            )
            continue
        except httpx.HTTPError as e:
            last_error = e
            logger.warning(f"Odds API key {idx}/{len(keys)} failed ({e}); trying next key")
            continue

    if data is None:
        logger.error("All Odds API keys failed")
        if last_error:
            raise last_error
        raise RuntimeError("All Odds API keys failed")
    
    games = []
    
    for game in data:
        game_id = game.get("id")
        away_team = game.get("away_team")
        home_team = game.get("home_team")
        commence_time = game.get("commence_time")
        
        # Extract Pinnacle odds from bookmakers
        pinnacle_away_ml = None
        pinnacle_home_ml = None
        
        for bookmaker in game.get("bookmakers", []):
            if bookmaker.get("key") != "pinnacle":
                continue
            
            # Pinnacle h2h markets: [away_odds, home_odds]
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                
                outcomes = market.get("outcomes", [])
                if outcomes:
                    # Match outcomes by team name to avoid ordering assumptions.
                    for outcome in outcomes:
                        name = outcome.get("name")
                        price = outcome.get("price")
                        if name == away_team:
                            pinnacle_away_ml = price
                        elif name == home_team:
                            pinnacle_home_ml = price
        
        if pinnacle_away_ml is not None and pinnacle_home_ml is not None:
            game_start_dt = _parse_iso8601_to_utc(commence_time)
            games.append(
                NBAGame(
                    id=game_id,
                    away_team=away_team,
                    home_team=home_team,
                    commence_time=commence_time,
                    pinnacle_away_ml=pinnacle_away_ml,
                    pinnacle_home_ml=pinnacle_home_ml,
                    game_start_time=game_start_dt,
                )
            )
        else:
            logger.debug(f"Skipping game (no Pinnacle odds): {away_team} @ {home_team}")
    
    logger.debug(f"Found {len(games)} NBA games with Pinnacle moneylines")
    return games


def main():
    """Quick test: fetch and print NBA games."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    api_keys = get_odds_api_keys_from_env()
    if not api_keys:
        logger.error("ODDS_API_KEY or ODDS_API_KEYS not found in environment")
        return 1
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    try:
        games = get_nba_games_with_pinnacle(api_keys)
        
        print("\n" + "=" * 100)
        print("NBA GAMES WITH PINNACLE MONEYLINES")
        print("=" * 100)
        
        for game in games:
            print(
                f"{game.away_team:20} @ {game.home_team:20} "
                f"| Away: {game.pinnacle_away_ml:+6d} | Home: {game.pinnacle_home_ml:+6d} "
                f"| {game.commence_time}"
            )
        
        print("=" * 100)
        print(f"Total: {len(games)} games")
        return 0
    
    except Exception as e:
        logger.error(f"Failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
