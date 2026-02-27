"""List simple NBA game winner markets."""
import sys
from pathlib import Path

# Add parent directory to path so we can import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kalshi_public import list_markets

print("Fetching NBA game winner markets...\n")

# Fetch markets with series_ticker filter
markets = list_markets(series_ticker='KXNBAGAME', limit=200)

print(f"Found {len(markets)} NBA game markets:\n")

for m in markets[:30]:
    ticker = m.get('ticker', 'N/A')
    status = m.get('status', 'unknown')
    title = m.get('title', 'N/A')[:70]
    
    # Get prices
    yes_bid = m.get('yes_bid', 0)
    no_bid = m.get('no_bid', 0)
    yes_ask = m.get('yes_ask', 0)
    no_ask = m.get('no_ask', 0)
    
    has_liquidity = yes_bid > 0 or no_bid > 0
    liquidity_marker = "💰" if has_liquidity else "  "
    
    print(f"{liquidity_marker} {ticker:45} {status:10}")
    if has_liquidity:
        print(f"   {title}")
        print(f"   YES: bid={yes_bid} ask={yes_ask}  NO: bid={no_bid} ask={no_ask}")

print(f"\n{len(markets)} total NBA game markets")
