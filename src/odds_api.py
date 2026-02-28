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
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Odds API endpoint
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


@dataclass(frozen=True)
class NBAGame:
    """Represents a matchup from Odds API."""
    id: str
    away_team: str
    home_team: str
    commence_time: str  # ISO 8601 timestamp
    pinnacle_away_ml: Optional[int]  # American odds
    pinnacle_home_ml: Optional[int]  # American odds


def get_nba_games_with_pinnacle(api_key: str) -> list[NBAGame]:
    """
    Fetch all NBA games with Pinnacle moneylines from The Odds API.
    
    Args:
        api_key: Your Odds API key (from .env or direct)
    
    Returns:
        List of NBAGame objects with Pinnacle moneylines
    
    Raises:
        httpx.HTTPError if API request fails
        ValueError if response is malformed
    """
    logger.debug("Fetching NBA games from Odds API with Pinnacle odds...")
    
    url = f"{ODDS_API_BASE}/sports/basketball_nba/odds"
    params = {
        "apiKey": api_key,
        "markets": "h2h",  # Moneyline only
        "bookmakers": "pinnacle",  # Only Pinnacle (sharpest)
        "oddsFormat": "american",
    }
    
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        
        # Log rate limit info
        remaining = response.headers.get("x-requests-remaining", "?")
        used = response.headers.get("x-requests-used", "?")
        logger.debug(f"API requests used: {used}, remaining: {remaining}")
        
    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise
    
    data = response.json()
    
    logger.debug(f"Fetched {len(data)} games from Odds API")
    
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
            games.append(
                NBAGame(
                    id=game_id,
                    away_team=away_team,
                    home_team=home_team,
                    commence_time=commence_time,
                    pinnacle_away_ml=pinnacle_away_ml,
                    pinnacle_home_ml=pinnacle_home_ml,
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
    
    # Try to get API key from environment, or use a fallback
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        logger.error("ODDS_API_KEY not found in environment")
        return 1
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    try:
        games = get_nba_games_with_pinnacle(api_key)
        
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
