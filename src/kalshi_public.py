from __future__ import annotations

import base64
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API endpoint for Kalshi (updated Feb 2026)
# Old endpoint (retired): https://trading-api.kalshi.com/trade-api/v2
# New endpoint: https://api.elections.kalshi.com/trade-api/v2
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KalshiTop:
    bid_yes: float | None
    bid_no: float | None
    ask_yes: float | None
    ask_no: float | None
    bid_yes_qty: int | None = None  # Total liquidity at best YES bid
    bid_no_qty: int | None = None  # Total liquidity at best NO bid
    ask_yes_qty: int | None = None  # Inferred from bid_no_qty (1-1 correspondence)
    ask_no_qty: int | None = None   # Inferred from bid_yes_qty (1-1 correspondence)


def _load_private_key(key_file_path: str):
    """Load an RSA private key from a PEM file."""
    logger.debug(f"Loading private key from {key_file_path}")
    path = Path(key_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Private key file not found: {key_file_path}")
    
    with open(path, "rb") as f:
        key_data = f.read()
        logger.debug(f"Key file size: {len(key_data)} bytes")
        
    private_key = serialization.load_pem_private_key(
        key_data,
        password=None,
        backend=None,
    )
    logger.debug(f"Successfully loaded private key (type: {type(private_key).__name__})")
    return private_key


def _sign_request(private_key, timestamp_ms: int, method: str, path: str, use_pkcs1: bool = False) -> str:
    """
    Sign a request using RSA.
    
    Default: RSA-PSS-SHA256 (more secure)
    Alternative: PKCS#1 v1.5 with SHA256 (if API requires it)
    
    Returns base64-encoded signature.
    """
    message = f"{timestamp_ms}{method}{path}".encode("utf-8")
    logger.debug(f"Signing message: '{timestamp_ms}{method}{path}'")
    logger.debug(f"Message bytes: {message}")
    
    if use_pkcs1:
        logger.debug("Using PKCS#1 v1.5 padding")
        signature = private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    else:
        logger.debug("Using RSA-PSS padding")
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
    
    sig_b64 = base64.b64encode(signature).decode("utf-8")
    logger.debug(f"Generated signature: {sig_b64[:80]}...")
    return sig_b64



def _to_dollars(price) -> float:
    """
    Normalize Kalshi prices to dollars.

    Integers are cents (1 -> 0.01). Floats <= 1 are dollars. Floats > 1 are cents.
    """
    if price is None:
        raise ValueError("price is None")

    if isinstance(price, bool):
        raise ValueError(f"price must be numeric, got {price}")

    if isinstance(price, int):
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")
        return price / 100.0

    p = float(price)
    if p <= 0.0:
        raise ValueError(f"price must be positive, got {price}")
    return p if p <= 1.0 else p / 100.0


def get_orderbook_top(
    ticker: str,
    key_id: Optional[str] = None,
    key_file_path: Optional[str] = None,
    use_pkcs1: bool = False,
) -> KalshiTop:
    """
    Pulls the orderbook (bids only) and infers asks using:
      ask_yes = 1 - bid_no
      ask_no  = 1 - bid_yes

    Authenticates using RSA-PSS signed headers.  If *key_id* and *key_file_path*
    are not provided, they will be read from environment variables:
      - KALSHI_KEY_ID
      - KALSHI_KEY_FILE
    """
    logger.debug(f"Fetching orderbook for {ticker}")
    
    # Get credentials from args or environment
    if key_id is None:
        key_id = os.getenv("KALSHI_KEY_ID")
    if key_file_path is None:
        key_file_path = os.getenv("KALSHI_KEY_FILE")
    
    if not key_id or not key_file_path:
        raise ValueError(
            "Must provide KALSHI_KEY_ID and KALSHI_KEY_FILE "
            "(via args, environment variables, or both)"
        )
    
    logger.debug(f"Using key ID: {key_id}")
    
    # Load private key
    private_key = _load_private_key(key_file_path)
    
    # Build request
    url = f"{KALSHI_BASE}/markets/{ticker}/orderbook"
    method = "GET"
    path = f"/trade-api/v2/markets/{ticker}/orderbook"
    
    # Sign request
    timestamp_ms = int(time.time() * 1000)
    signature = _sign_request(private_key, timestamp_ms, method, path, use_pkcs1=use_pkcs1)
    
    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
        "KALSHI-ACCESS-SIGNATURE": signature,
    }
    
    logger.debug(f"Making request to {url}")
    logger.debug(f"Headers: KALSHI-ACCESS-KEY={key_id}, KALSHI-ACCESS-TIMESTAMP={timestamp_ms}, KALSHI-ACCESS-SIGNATURE={signature[:40]}...")
    
    r = httpx.get(url, timeout=10.0, headers=headers)
    logger.debug(f"Response status: {r.status_code}")
    
    if r.status_code == 401:
        logger.error(
            f"Unauthorized (401) - verify:\n"
            f"  1. Key ID is correct: {key_id}\n"
            f"  2. Private key file exists and is valid: {key_file_path}\n"
            f"  3. Key is activated in Kalshi dashboard\n"
            f"  4. Signature algorithm matches API expectations"
        )
    
    r.raise_for_status()
    data = r.json()
    
    logger.debug(f"Fetched orderbook for {ticker}")

    # The docs describe "yes bids" and "no bids" arrays.
    # We’ll be defensive in parsing since field names can vary slightly.
    ob = data.get("orderbook", data)
    
    # Log the orderbook structure if we can't find expected fields
    if "orderbook" in data:
        logger.debug(f"Orderbook keys: {list(ob.keys())}")
    else:
        logger.warning(f"No 'orderbook' key in response. Top-level keys: {list(data.keys())}")

    yes_bids = ob.get("yes", ob.get("yes_bids", [])) or []
    no_bids = ob.get("no", ob.get("no_bids", [])) or []
    
    if not yes_bids and not no_bids:
        logger.debug(f"Empty orderbook for {ticker}: yes_bids={yes_bids}, no_bids={no_bids}")

    def best_bid(bids):
        # Each entry is typically [price, quantity] or {"price":..., "quantity":...}.
        # Kalshi may return bids sorted by price ascending, so select the max price.
        if not bids:
            return None, None

        def extract_price_and_quantity(entry):
            if isinstance(entry, (list, tuple)):
                price = _to_dollars(entry[0])
                quantity = entry[1] if len(entry) > 1 else 0
                return (price, quantity)
            if isinstance(entry, dict):
                price = _to_dollars(entry.get("price")) if entry.get("price") is not None else None
                quantity = entry.get("quantity", 0)
                return (price, quantity)
            return (None, 0)

        price_qty_pairs = [extract_price_and_quantity(entry) for entry in bids]
        price_qty_pairs = [(p, q) for p, q in price_qty_pairs if p is not None]
        
        if not price_qty_pairs:
            return None, None
            
        best_price = max(p for p, q in price_qty_pairs)
        total_liquidity = sum(q for p, q in price_qty_pairs if p == best_price)
        
        logger.debug(f"  Best bid: ${best_price:.2f} with {total_liquidity} contracts available")
        return best_price, total_liquidity

    bid_yes, bid_yes_qty = best_bid(yes_bids)
    bid_no, bid_no_qty = best_bid(no_bids)

    ask_yes = (1.0 - bid_no) if bid_no is not None else None
    ask_no = (1.0 - bid_yes) if bid_yes is not None else None

    return KalshiTop(
        bid_yes=bid_yes,
        bid_no=bid_no,
        ask_yes=ask_yes,
        ask_no=ask_no,
        bid_yes_qty=bid_yes_qty,
        bid_no_qty=bid_no_qty,
        ask_yes_qty=bid_no_qty,  # Inferred: buying YES at ask = selling NO at bid
        ask_no_qty=bid_yes_qty,  # Inferred: buying NO at ask = selling YES at bid
    )


def list_markets(
    key_id: Optional[str] = None,
    key_file_path: Optional[str] = None,
    search_filter: Optional[str] = None,
    use_pkcs1: bool = False,
    series_ticker: Optional[str] = None,
    limit: int = 1000,
) -> list[dict]:
    """
    List available markets from Kalshi.
    
    Args:
        search_filter: Filter by ticker substring (e.g. 'kxnbagame' for NBA games)
        series_ticker: Filter by series (e.g. 'KXNBAGAME' for NBA game winners)
        limit: Maximum markets to fetch (default 1000)
    """
    logger.debug("Fetching market list from Kalshi")
    
    if key_id is None:
        key_id = os.getenv("KALSHI_KEY_ID")
    if key_file_path is None:
        key_file_path = os.getenv("KALSHI_KEY_FILE")
    
    if not key_id or not key_file_path:
        raise ValueError(
            "Must provide KALSHI_KEY_ID and KALSHI_KEY_FILE "
            "(via args, environment variables, or both)"
        )
    
    private_key = _load_private_key(key_file_path)
    
    all_markets = []
    cursor = None
    
    while len(all_markets) < limit:
        # Build URL with query params
        base_url = f"{KALSHI_BASE}/markets"
        query_params = []
        
        if series_ticker:
            query_params.append(f"series_ticker={series_ticker}")
        if cursor:
            query_params.append(f"cursor={cursor}")
        
        url = base_url + ("?" + "&".join(query_params) if query_params else "")
        
        method = "GET"
        path = "/trade-api/v2/markets" + ("?" + "&".join(query_params) if query_params else "")
        
        timestamp_ms = int(time.time() * 1000)
        signature = _sign_request(private_key, timestamp_ms, method, path, use_pkcs1=use_pkcs1)
        
        headers = {
            "KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
            "KALSHI-ACCESS-SIGNATURE": signature,
        }
        
        logger.debug(f"Making request to {url}")
        r = httpx.get(url, timeout=10.0, headers=headers)
        logger.debug(f"Response status: {r.status_code}")
        
        if r.status_code == 401:
            logger.error(f"Unauthorized (401) - check key permissions and endpoint: {url}")
        
        r.raise_for_status()
        
        data = r.json()
        batch = data.get("markets", [])
        all_markets.extend(batch)
        
        logger.debug(f"Retrieved {len(batch)} markets (total so far: {len(all_markets)})")
        
        # Check for more pages
        cursor = data.get("cursor")
        if not cursor or len(batch) == 0:
            break
    
    logger.debug(f"Total markets retrieved: {len(all_markets)}")
    
    # Apply text filter if provided
    if search_filter:
        all_markets = [m for m in all_markets if search_filter.lower() in m.get("ticker", "").lower()]
        logger.debug(f"Filtered to {len(all_markets)} markets matching '{search_filter}'")
    
    return all_markets


def get_market_details(
    ticker: str,
    key_id: Optional[str] = None,
    key_file_path: Optional[str] = None,
    use_pkcs1: bool = False,
) -> dict:
    """
    Fetch market details for a specific ticker (includes status, prices, etc).
    
    Args:
        ticker: Market ticker
        key_id: Kalshi API key ID (or KALSHI_KEY_ID env var)
        key_file_path: Path to private key PEM (or KALSHI_KEY_FILE env var)
    
    Returns:
        Market details dict with fields like: ticker, status, title, yes_bid, no_bid, etc.
    """
    logger.debug(f"Fetching market details for {ticker}")
    
    if key_id is None:
        key_id = os.getenv("KALSHI_KEY_ID")
    if key_file_path is None:
        key_file_path = os.getenv("KALSHI_KEY_FILE")
    
    if not key_id or not key_file_path:
        raise ValueError(
            "Must provide KALSHI_KEY_ID and KALSHI_KEY_FILE "
            "(via args, environment variables, or both)"
        )
    
    private_key = _load_private_key(key_file_path)
    
    url = f"{KALSHI_BASE}/markets/{ticker}"
    method = "GET"
    path = f"/trade-api/v2/markets/{ticker}"
    
    timestamp_ms = int(time.time() * 1000)
    signature = _sign_request(private_key, timestamp_ms, method, path, use_pkcs1=use_pkcs1)
    
    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
        "KALSHI-ACCESS-SIGNATURE": signature,
    }
    
    logger.debug(f"Making request to {url}")
    r = httpx.get(url, timeout=10.0, headers=headers)
    logger.debug(f"Response status: {r.status_code}")
    
    if r.status_code == 401:
        logger.error(f"Unauthorized (401) for market details: {ticker}")
    
    r.raise_for_status()
    data = r.json()
    
    market = data.get("market", data)
    logger.debug(f"Market details: ticker={market.get('ticker')}, status={market.get('status')}")
    
    return market