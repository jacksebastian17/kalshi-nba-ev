# kalshi-nba-ev

NBA arbitrage detector comparing Pinnacle moneylines to Kalshi prediction markets.

## Overview

Fetches Pinnacle NBA odds, de-vigs to fair probabilities, compares to Kalshi prices, and identifies +EV opportunities.

**V2 Update:** Now accounts for Kalshi's fee structure (10% of potential profit), applies 70¢ minimum price filter, and uses 7% edge threshold.

## Fee Structure

Kalshi charges **10% of potential profit** (not flat per-contract fees):

```
Fee = 10% × (1 - contract_price)
```

Examples:
- 20¢ contract: 8¢ fee (40% of price) ❌
- 70¢ contract: 3¢ fee (4.3% of price) ✓
- 80¢ contract: 2¢ fee (2.5% of price) ✓

**Result:** Only contracts >= 70¢ are profitable after fees.

**Volume tiers:** 10% (default) → 7% ($25k/mo) → 5% ($100k/mo) → 2% ($500k/mo)

## Quick Start

### Setup

1. Copy `.env.example` to `.env` and fill in:
   - `KALSHI_KEY_ID` and `KALSHI_KEY_FILE` (from Kalshi dashboard)
   - `ODDS_API_KEY` (free tier: 500 requests/month at the-odds-api.com)

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Automated Scanner (Recommended)

Scans all NBA games automatically:

```bash
python scan.py
```

**Output format:**
```
Portland Trail Blazers @ Charlotte Hornets    | Pinnacle:   +270/  -327
  Portland Trail Blazers | p=0.261 | Y:0.28 N:0.73 | raw_y=-0.019 raw_n=+0.009 | fee=0.073 net=-0.069 | SKIP
  Charlotte Hornets     | p=0.739 | Y:0.74 N:0.27 | raw_y=-0.001 raw_n=-0.009 | fee=0.026 net=-0.031 | SKIP
```

**Column meanings:**
- `p` = De-vigged probability from Pinnacle
- `Y:0.28` = Kalshi YES ask price (cents)
- `N:0.73` = Kalshi NO ask price (cents)
- `raw_y` = Raw edge before fees (YES side)
- `raw_n` = Raw edge before fees (NO side)
- `fee` = Kalshi fee amount per contract
- `net` = Net edge after fees and slippage
- `SKIP` / `BUY_YES` / `BUY_NO` = Decision

### Manual CLI (Advanced)

Test single market:
```bash
python -m src.cli --ticker KXNBAGAME-26FEB27CLEDET-DET --action top
```

Evaluate with odds (fee-aware parameters):
```bash
python -m src.cli --ticker KXNBAGAME-26FEB27CLEDET-DET \
  --amer-yes +212 \
  --amer-no -248 \
  --fee-rate 0.10 \           # 10% fee (change to 0.07 if $25k+/month volume)
  --min-price 0.70 \          # Skip contracts < 70¢ (fees too high)
  --edge-threshold 0.07 \     # 7% threshold (accounts for fees + slippage)
  --action eval
```

**Default parameters:**
- `fee_rate=0.10` (10% for typical traders)
- `min_price=0.70` (filter out expensive fees)
- `edge_threshold=0.07` (7% minimum net edge)

## Architecture

**Core Modules:**
- `math_utils` – Odds conversion, de-vig, edge calculation, fee calculation (`kalshi_fee()`)
- `sharp_model` – Proportional de-vig (removes bookmaker margin)
- `odds_api` – Pinnacle moneylines via The Odds API
- `kalshi_public` – RSA-PSS authentication, orderbook fetching
- `game_matcher` – Team name → Kalshi ticker mapping
- `decision` – Fee-aware BUY_YES/BUY_NO/SKIP logic (7% threshold, 70¢ filter, 10% fees)
- `scanner` – Single market evaluation
- `batch_scanner` – Multi-market evaluation
- `scan.py` – Automated scanner (CLI)
- `cli.py` – Manual testing tool

## How It Works

1. Fetch Pinnacle odds (e.g., CLE +212, DET -248)
2. Convert to decimal (3.12, 1.40)
3. Calculate implied probabilities (32.1%, 71.4%)
4. De-vig using proportional method (31.0%, 69.0%)
5. Build Kalshi tickers (KXNBAGAME-26FEB28CLEDET-CLE, etc.)
6. Fetch Kalshi orderbook prices (ask_yes, ask_no)
7. Calculate raw edges: `p_true - price`
8. Calculate fees: `10% × (1 - price)`
9. Calculate net edge: `raw_edge - fee - slippage`
10. Filter: Skip if price < 70¢ or net edge < 7%
11. Return decision: BUY_YES / BUY_NO / SKIP

## Testing

```bash
pytest  # 30 tests, all passing (includes fee-aware logic and edge filtering)
```

Key test additions:
- `test_kalshi_fee()` – Verify 10% × (1-price) calculation
- `test_kalshi_edge_after_fees()` – Verify edge subtraction with slippage
- `test_skip_when_price_too_low()` – Verify 70¢ filter rejects cheap contracts

## Known Limitations

- **Odds API cache:** 30-60s server-side cache (not real-time)
- **Kalshi fees:** 2-10% depending on volume/price, destroys small edges
- **Mainstream efficiency:** NBA moneylines typically 1-3% mismatches (need 7%+ after fees)
- **Moneylines only:** No player props, spreads, or totals
- **No auto-execution:** Manual trading required
- **No news monitoring:** Can't detect injuries/lineup changes in real-time

## Next Steps

**High Priority:**
- [ ] News monitoring (ESPN/Twitter API for injury alerts)
- [ ] Player props support (expand beyond moneylines)
- [ ] Real-time websocket feeds (remove API cache delay)
- [ ] Auto-execution (place orders programmatically)

**Medium Priority:**
- [ ] CLV tracking (log closing line value)
- [ ] Kelly criterion position sizing
- [ ] Multiple sportsbooks (DraftKings, FanDuel)
- [ ] Historical analysis dashboard

**Research:**
- [ ] Compare de-vig methods (power law, additive, odds-ratio)
- [ ] Analyze line movement velocity
- [ ] Test volume/price correlation with edge quality

## License

MIT
