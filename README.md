# kalshi-nba-ev

NBA +EV detector comparing Pinnacle moneylines to Kalshi prediction markets.

## Overview

Fetches Pinnacle NBA odds, de-vigs to fair probabilities, compares to Kalshi prices, and identifies +EV opportunities.

**V3 Update (Feb 2026):** Fixed fee calculation to use official Kalshi formula `ceil_to_cent(0.07 * contracts * P * (1 - P))` with symmetric fees peaking at P=0.50. Now supports trading cheaper markets with good edges.

## Fee Structure

Kalshi charges a **taker fee of 7%** based on a quadratic formula:

```
Fee = ceil_to_cent(0.07 * contracts * P * (1 - P))
```

where P is the contract price (0–1).

**Key differences from old model:**
- Old: fee peaked at 0% (expensive for cheap contracts)
- New: fee peaks at 50% (symmetric: fee(20¢) ≈ fee(80¢))

Examples (taker fees, per contract):
- 5¢ contract: ceil(0.07 × 0.05 × 0.95) = $0.01
- 30¢ contract: ceil(0.07 × 0.30 × 0.70) = $0.02
- 50¢ contract: ceil(0.07 × 0.50 × 0.50) = $0.02 (peak)
- 95¢ contract: ceil(0.07 × 0.95 × 0.05) = $0.01

**Result:** Can now profitably trade cheaper markets with good edges! No longer limited to 70¢+ contracts.

**Maker fees (optional):** Half the taker rate at 1.75%, e.g., ceil_to_cent(0.0175 * contracts * P * (1 - P))

## Quick Start

### Setup

1. Copy `.env.example` to `.env` and fill in:
   - `KALSHI_KEY_ID` and `KALSHI_KEY_FILE` (from Kalshi dashboard)
   - `ODDS_API_KEY` (free tier: 500 requests/month at the-odds-api.com)
  - Optional rotation: `ODDS_API_KEYS=key1,key2,key3` (comma-separated; tried in order)

If `ODDS_API_KEYS` is set, it takes precedence over `ODDS_API_KEY`.

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Automated Scanner (Recommended)

Scans all NBA games automatically:

```bash
python scan.py
```

### Continuous Background Scanner (Every 5 Minutes)

Run indefinitely (foreground):

```bash
python run_background_scan.py
```

Run in background on PowerShell:

```powershell
Start-Process python -ArgumentList "run_background_scan.py" -WindowStyle Hidden
```

Notes:
- Edit `SCAN_INTERVAL_SECONDS` in `run_background_scan.py` to change cadence.
- `scan.py` keeps your in-code live-mode settings (`LIVE_MODE`, `MIN_NET_EDGE`, etc.).

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
python -m src.cli --ticker KXNBAGAME-26FEB28CLEDET-DET \
  --amer-yes +212 \
  --amer-no -248 \
  --action eval
```

Advanced options:
```bash
python -m src.cli --ticker KXNBAGAME-26FEB28CLEDET-DET \
  --amer-yes +212 \
  --amer-no -248 \
  --min-price 0.30 \          # Allow contracts >= 30¢ (default 5¢)
  --edge-threshold 0.10 \     # 10% threshold (stricter, default 7%)
  --action eval
```

**Default parameters:**
- `fee_maker=False` (use taker fee; set to True for maker rebates if available)
- `min_price=0.05` (allow cheap markets; fees are symmetric around 50¢)
- `edge_threshold=0.07` (7% minimum net edge after all costs)

## Architecture

**Core Modules:**
- `math_utils` – Odds conversion, de-vig, edge calculation, fee calculation (`kalshi_fee()`)
- `sharp_model` – Proportional de-vig (removes bookmaker margin)
- `odds_api` – Pinnacle moneylines via The Odds API
- `kalshi_public` – RSA-PSS authentication, orderbook fetching
- `game_matcher` – Team name → Kalshi ticker mapping
- `decision` – Fee-aware BUY_YES/BUY_NO/SKIP logic (7% threshold, symmetric fees)
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
8. Calculate taker fees: `ceil_to_cent(0.07 * contracts * P * (1 - P))`
9. Calculate net edge: `raw_edge - fee - slippage`
10. Filter: Skip if net edge < 7% (default; configurable)
11. Return decision: BUY_YES / BUY_NO / SKIP

## Testing

```bash
pytest  # 47 tests, all passing (includes corrected fee formula and edge filtering)
```

Key test additions:
- `test_kalshi_fee_taker_at_*` – Verify correct fee calculation at key prices (5¢, 30¢, 50¢, 95¢)
- `test_kalshi_fee_taker_symmetry()` – Verify fee symmetry (fee(20¢) = fee(80¢))
- `test_kalshi_edge_after_fees_*` – Verify net edge calculation with new fees
- `test_cheap_market_with_good_edge()` – Verify we can trade cheap markets
- `test_expensive_market_with_modest_edge()` – Verify expensive markets need bigger edges

## Known Limitations
1-2% at extremes, peak 2% at 50¢ (destroys small edges)
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
