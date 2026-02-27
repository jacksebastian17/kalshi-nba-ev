"""Check the raw markets API response structure."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
import httpx
import time
import base64
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Load credentials
key_file = os.getenv('KALSHI_KEY_FILE')
key_id = os.getenv('KALSHI_KEY_ID')

with open(key_file, 'rb') as f:
    key = serialization.load_pem_private_key(f.read(), password=None)

# Make request
path = '/trade-api/v2/markets'
ts = int(time.time() * 1000)
msg = f'{ts}GET{path}'.encode()
sig = base64.b64encode(
    key.sign(
        msg,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256()
    )
).decode()

url = f'https://api.elections.kalshi.com{path}'
headers = {
    'KALSHI-ACCESS-KEY': key_id,
    'KALSHI-ACCESS-TIMESTAMP': str(ts),
    'KALSHI-ACCESS-SIGNATURE': sig
}

print("Making request to:", url)
r = httpx.get(url, headers=headers, timeout=10.0)
print(f"Status: {r.status_code}\n")

data = r.json()

# Check response structure
print("Response keys:", list(data.keys()))
print(f"\nNumber of markets: {len(data.get('markets', []))}")

# Check for pagination info
if 'cursor' in data:
    print(f"Cursor: {data['cursor']}")
if 'has_more' in data:
    print(f"Has more: {data['has_more']}")

# Show first market structure
if data.get('markets'):
    print("\nFirst market structure:")
    print(json.dumps(data['markets'][0], indent=2))
