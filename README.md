# kalshi-nba-ev

NBA arbitrage detector comparing Pinnacle moneylines to Kalshi prediction markets.

## Overview

Fetches sharp Pinnacle NBA odds via The Odds API, de-vigs to get fair probabilities, then compares to Kalshi prediction market prices to identify +EV opportunities.

**Current scope:** Moneylines only (1:1 mapping, highest confidence).

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

**Output:**
```
Cleveland Cavaliers  @ Detroit Pistons      | Pinnacle:   +212/  -248
  Cleveland Cavaliers | p=0.310 | Y:0.31 N:0.71 | edge_y=+0.000 edge_n=-0.020 | SKIP
  Detroit Pistons     | p=0.690 | Y:0.71 N:0.30 | edge_y=-0.020 edge_n=+0.010 | SKIP
```

Shows:
- **p** = true probability (de-vigged from Pinnacle)
- **Y/N** = Kalshi ask prices (YES/NO)
- **edge_y/edge_n** = raw edge on each side (before slippage buffer)

### Manual CLI (Advanced)

Test single market:
```bash
python -m src.cli --ticker KXNBAGAME-26FEB27CLEDET-DET --action top
```

Evaluate with odds:
```bash
python -m src.cli --ticker KXNBAGAME-26FEB27CLEDET-DET --amer-yes +212 --amer-no -248 --action eval
```

## Architecture

**Core Math:**
- `math_utils` – American/decimal odds conversion, edge calculation
- `sharp_model` – proportional de-vig (remove bookmaker margin)

**Data Sources:**
- `odds_api` – Pinnacle moneylines via The Odds API
- `kalshi_public` – RSA-PSS authentication, orderbook fetching
- `game_matcher` – team name → Kalshi ticker mapping (35 NBA teams)

**Decision Logic:**
- `decision` – BUY_YES/BUY_NO/SKIP (2% edge threshold, 0.5% slippage buffer)
- `scanner` – single market evaluation
- `batch_scanner` – multi-market scan

**Interfaces:**
- `scan.py` – automated scanner (recommended for live monitoring)
- `cli.py` – manual command-line tool

## How It Works

1. **Fetch Pinnacle odds** (e.g., CLE +212, DET -248)
2. **Convert to decimal** (3.12, 1.40)
3. **Calculate implied probabilities** (0.321, 0.712 — sum > 1 due to vig)
4. **De-vig** (proportional: 0.310, 0.690 — fair market)
5. **Build Kalshi ticker** (KXNBAGAME-26FEB27CLEDET-DET)
6. **Fetch Kalshi prices** (ask_yes=0.71, ask_no=0.30)
7. **Calculate edge** (p_true - ask_price)
8. **Decide:** BUY if edge > 2% (after 0.5% slippage buffer), else SKIP

## Testing

```bash
pytest  # 27 tests, all passing
```

## Known Limitations

- **Odds API cache:** 30-60s server-side cache (not real-time)
- **Kalshi liquidity:** Wide spreads, low volume
- **Moneylines only:** No player props, spreads, or totals (yet)
- **No CLV tracking:** Data logging not yet implemented

## Next Steps (V2)

- [ ] Monitoring loop (poll every 5-10 minutes)
- [ ] SQLite database for CLV tracking
- [ ] Twilio SMS alerts for opportunities
- [ ] Historical analysis dashboard
- [ ] Direct Pinnacle scraper (bypass cache)

## License

MIT
