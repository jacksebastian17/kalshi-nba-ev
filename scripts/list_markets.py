"""Quick script to list markets from Kalshi."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kalshi_public import list_markets

# Get all markets
print("Fetching all markets...\n")
all_markets = list_markets()

print(f"Total markets available: {len(all_markets)}\n")

# Group by ticker prefix
from collections import defaultdict
by_prefix = defaultdict(int)
for m in all_markets:
    ticker = m.get('ticker', '')
    prefix = ticker.split('-')[0] if '-' in ticker else ticker[:10]
    by_prefix[prefix] += 1

print("Market types (by ticker prefix):")
for prefix, count in sorted(by_prefix.items(), key=lambda x: -x[1])[:20]:
    print(f"  {prefix:40} {count:4} markets")

print("\n" + "="*80)
print("\nSample markets:")
for m in all_markets[:5]:
    ticker = m.get('ticker', 'N/A')
    title = m.get('title', 'N/A')[:80]
    status = m.get('status', 'unknown')
    print(f"\nTicker: {ticker}")
    print(f"Title:  {title}")
    print(f"Status: {status}")


