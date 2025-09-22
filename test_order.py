import os
import uuid
import requests
from kalshi_bot.client import KalshiHttpClient, Environment
from cryptography.hazmat.primitives import serialization

# Load private key from PEM file
with open("demo_private.pem", "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

# Create client
client = KalshiHttpClient(
    key_id=os.getenv("KALSHI_API_KEY_ID"),   # must be set in .env
    private_key=private_key,
    environment=Environment.DEMO
)

# Check balance
print("Balance:", client.get_balance())
try:
    order = client.place_order({
    "ticker": "KXQUICKSETTLE-25SEP21H0610-2",  # 👈 copy from list_open_markets.py
    "action": "buy",
    "side": "yes",
    "count": 1,
    "type": "limit",
    "yes_price": 10,  # bid 10 cents just for testing
    "client_order_id": str(uuid.uuid4())
    })
    print("Order response:", order)

except requests.exceptions.HTTPError as e:
    print("HTTPError:", e.response.status_code, e.response.text)


