# kalshi-nba-ev

NBA arbitrage engine for Kalshi markets.

## Quick Start

Credentials are in .env - they load automatically.

Install:
```
pip install -r requirements.txt
```

Test connection:
```
python -m src.cli --ticker KXNBAGAME-26FEB27CLEDET-DET --action top
```

Evaluate market:
```
python -m src.cli --ticker KXNBAGAME-26FEB27CLEDET-DET --amer-yes -110 --amer-no -110 --action eval
```

Batch scan:
```
python -m src.cli --filter "KXNBAGAME-26FEB27" --amer-yes -110 --amer-no -110 --action batch
```

## Architecture

- **math_utils** – odds conversions and EV
- **sharp_model** – de-vig sportsbook lines  
- **kalshi_public** – RSA-PSS auth + API client (api.elections.kalshi.com)
- **decision** – BUY_YES/BUY_NO/SKIP logic
- **scanner** – single market eval
- **batch_scanner** – multi-market scan with pagination
- **cli** – command interface

## Testing

```
pytest
```
