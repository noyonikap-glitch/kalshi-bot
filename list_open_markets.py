import os
import json
import uuid
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from kalshi_bot.client import KalshiHttpClient, Environment

# Load .env
load_dotenv()

# Load private key
with open("demo_private.pem", "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

# Create client
client = KalshiHttpClient(
    key_id=os.getenv("KALSHI_API_KEY_ID"),
    private_key=private_key,
    environment=Environment.DEMO
)

print("Fetching open markets...\n")
markets = client.get("/trade-api/v2/markets", params={"status": "open", "limit": 10})
print(json.dumps(markets, indent=2))

print("\nCopy a ticker from above and paste it into your test_order.py payload!")

