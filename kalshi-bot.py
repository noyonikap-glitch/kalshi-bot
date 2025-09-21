import os
import time
import math
import json
import backoff
import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("KALSHI_BASE_URL", "https://demo-api.kalshi.co/trade-api/v2")
EMAIL = os.getenv("KALSHI_EMAIL")
PASSWORD = os.getenv("KALSHI_PASSWORD")

# --- Risk/strategy knobs (tune these) ---
QUOTE_TICKER = os.getenv("QUOTE_TICKER", "")  # e.g. set to a specific market ticker if you want
MAX_NOTIONAL_CENTS = int(os.getenv("MAX_NOTIONAL_CENTS", "20000"))  # $200 = 20000 cents
PER_ORDER_SIZE = int(os.getenv("PER_ORDER_SIZE", "1"))             # 1 contract per quote
SPREAD_CENTS = int(os.getenv("SPREAD_CENTS", "4"))                 # widen/narrow your quotes
INVENTORY_CAP = int(os.getenv("INVENTORY_CAP", "20"))              # max net YES
PNL_STOP_CENTS = int(os.getenv("PNL_STOP_CENTS", "-3000"))         # stop if PnL < -$30
MIN_BOOK_DEPTH = int(os.getenv("MIN_BOOK_DEPTH", "1"))             # require at least depth
POLL_SEC = float(os.getenv("POLL_SEC", "2.0"))                     # polling cadence (no WS here)

# ---- HTTP client with session + retry/backoff ----

class KalshiClient:
    def __init__(self, base_url: str, email: Optional[str] = None, password: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"Content-Type": "application/json"})
        self.email = email
        self.password = password

    @backoff.on_exception(backoff.expo, (requests.RequestException,), max_time=60)
    def _req(self, method: str, path: str, **kw) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        r = self.s.request(method, url, timeout=15, **kw)
        if r.status_code == 401:
            # attempt re-login once
            self.login()
            r = self.s.request(method, url, timeout=15, **kw)
        r.raise_for_status()
        if r.text.strip() == "":
            return {}
        return r.json()

    def login(self):
        if not self.email or not self.password:
            raise RuntimeError("No credentials set for email/password login.")
        payload = {"email": self.email, "password": self.password}
        # demo typically uses /login or /members/login; we use trade-api login:
        res = self._req("POST", "/login", json=payload)
        # session cookie set into self.s automatically via response cookies
        return res

    # --- API helpers (v2 style endpoints commonly used) ---
    def me(self) -> Dict[str, Any]:
        return self._req("GET", "/members/self")

    def get_markets(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._req("GET", "/markets", params=params or {})

    def get_market(self, ticker: str) -> Dict[str, Any]:
        return self._req("GET", f"/markets/{ticker}")

    def get_orderbook(self, ticker: str) -> Dict[str, Any]:
        return self._req("GET", f"/markets/{ticker}/orderbook")

    def list_positions(self) -> Dict[str, Any]:
        return self._req("GET", "/positions")

    def list_orders(self, ticker: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if ticker: params["ticker"] = ticker
        if status: params["status"] = status
        return self._req("GET", "/orders", params=params)

    def place_order(self, *, action: str, ticker: str, side: str, price: int, size: int,
                    order_type: str = "LIMIT", tif: str = "GTC") -> Dict[str, Any]:
        payload = {
            "action": action,     # "BUY" or "SELL"
            "ticker": ticker,
            "type": order_type,   # "LIMIT"
            "time_in_force": tif, # "GTC", "IOC", etc. (GTC safest here)
            "side": side,         # "YES" or "NO"
            "price": price,       # in cents (0..100)
            "size": size
        }
        return self._req("POST", "/orders", json=payload)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return self._req("DELETE", f"/orders/{order_id}")

    def account(self) -> Dict[str, Any]:
        return self._req("GET", "/accounts/self")

# --- Tiny utilities ---

@dataclass
class BookQuote:
    yes_bid: Optional[int]
    yes_ask: Optional[int]
    no_bid: Optional[int]
    no_ask: Optional[int]

def top_of_book(orderbook: Dict[str, Any]) -> BookQuote:
    # orderbook structure typically has "yes" and "no" sides with arrays of [price,size]
    yes_bids = orderbook.get("yes", {}).get("bids", [])
    yes_asks = orderbook.get("yes", {}).get("asks", [])
    no_bids  = orderbook.get("no",  {}).get("bids", [])
    no_asks  = orderbook.get("no",  {}).get("asks", [])
    yb = yes_bids[0][0] if len(yes_bids) >= 1 else None
    ya = yes_asks[0][0] if len(yes_asks) >= 1 else None
    nb = no_bids[0][0]  if len(no_bids)  >= 1 else None
    na = no_asks[0][0]  if len(no_asks)  >= 1 else None
    return BookQuote(yb, ya, nb, na)

def implied_mid(quote: BookQuote) -> Optional[float]:
    # Compute a mid for YES leg (fallback to 0..100 if missing)
    if quote.yes_bid is None and quote.yes_ask is None:
        return None
    if quote.yes_bid is None: return float(quote.yes_ask)
    if quote.yes_ask is None: return float(quote.yes_bid)
    return (quote.yes_bid + quote.yes_ask) / 2.0

# --- Risk / accounting (very rough) ---

@dataclass
class RiskState:
    cash_cents: int = 0
    net_yes: int = 0
    realized_pnl_cents: int = 0

def fetch_position_for_ticker(positions: Dict[str, Any], ticker: str) -> Tuple[int, int]:
    """Return net YES and approximate book value cents (rough)."""
    net_yes = 0
    bv = 0
    for p in positions.get("positions", []):
        if p.get("ticker") == ticker and p.get("leg") == "YES":
            # p might include fields like "size", "avg_price"
            net_yes += int(p.get("size", 0))
    return net_yes, bv

# --- Strategy: quote around mid with a fixed spread; keep inventory bounded ---

def choose_quotes(quote: BookQuote, spread_cents: int) -> Tuple[Optional[int], Optional[int]]:
    """
    Return (buy_price_yes, sell_price_yes) we want to quote.
    We target mid, then offset by half-spread. Clamp to [1,99].
    """
    mid = implied_mid(quote)
    if mid is None:
        return None, None
    buy_price = int(max(1, min(99, math.floor(mid - spread_cents / 2))))
    sell_price = int(max(1, min(99, math.ceil (mid + spread_cents / 2))))
    if buy_price >= sell_price:  # avoid crossed quotes
        buy_price = max(1, sell_price - 1)
    return buy_price, sell_price

# --- Main bot loop ---

def main():
    client = KalshiClient(BASE_URL, EMAIL, PASSWORD)
    print("[*] Logging in...")
    client.login()
    me = client.me()
    print(f"[*] Logged in as: {me.get('member', {}).get('email')}")

    acct = client.account()
    buying_power = acct.get("account", {}).get("buying_power_cents", 0)
    print(f"[*] Buying power (¢): {buying_power}")

    # Pick a market: either env ticker or first tradable one
    ticker = QUOTE_TICKER
    if not ticker:
        mk = client.get_markets(params={"limit": 50, "status": "open"})
        markets = mk.get("markets", [])
        if not markets:
            print("No open markets found; exiting.")
            return
        ticker = markets[0]["ticker"]
    print(f"[*] Target market: {ticker}")

    # Track outstanding order IDs to manage/cancel our own quotes
    my_orders: Dict[str, Dict[str, Any]] = {}

    risk = RiskState(
        cash_cents=buying_power,
        net_yes=0,
        realized_pnl_cents=0
    )

    while True:
        try:
            # Safety: refresh acct + positions
            acct = client.account()
            buying_power = acct.get("account", {}).get("buying_power_cents", 0)
            pos = client.list_positions()
            net_yes, _ = fetch_position_for_ticker(pos, ticker)
            risk.net_yes = net_yes

            if buying_power < 0 or buying_power < (PER_ORDER_SIZE * 100):
                print("[!] Low buying power; pausing quotes.")
                time.sleep(POLL_SEC)
                continue

            if risk.realized_pnl_cents <= PNL_STOP_CENTS:
                print(f"[!] PnL stop hit ({risk.realized_pnl_cents}¢); exiting.")
                break

            if abs(risk.net_yes) >= INVENTORY_CAP:
                print(f"[!] Inventory cap reached (net_yes={risk.net_yes}); quoting one side only.")

            # Get book & compute quotes
            ob = client.get_orderbook(ticker)
            q = top_of_book(ob.get("orderbook", ob))  # tolerate either wrapping
            if q.yes_bid is None and q.yes_ask is None:
                print("[!] No book; waiting…")
                time.sleep(POLL_SEC)
                continue

            buy_px, sell_px = choose_quotes(q, SPREAD_CENTS)

            # Simple logic: cancel stale working orders, then re-post fresh quotes
            # Cancel our working orders first
            existing = client.list_orders(ticker=ticker, status="working")
            for o in existing.get("orders", []):
                oid = o.get("order_id")
                if oid and o.get("owner") == me.get("member", {}).get("id"):
                    try:
                        client.cancel_order(oid)
                    except Exception as e:
                        print(f"[cancel warn] {e}")

            # Post buy quote (YES) if inventory allows
            if buy_px and risk.net_yes < INVENTORY_CAP:
                try:
                    r = client.place_order(
                        action="BUY",
                        ticker=ticker,
                        side="YES",
                        price=int(buy_px),
                        size=PER_ORDER_SIZE,
                        order_type="LIMIT",
                        tif="GTC",
                    )
                    oid = r.get("order", {}).get("order_id")
                    if oid: my_orders[oid] = r["order"]
                    print(f"[quote] BUY YES {PER_ORDER_SIZE}@{buy_px}")
                except Exception as e:
                    print(f"[buy error] {e}")

            # Post sell quote (YES) if inventory allows
            if sell_px and risk.net_yes > -INVENTORY_CAP:
                try:
                    r = client.place_order(
                        action="SELL",
                        ticker=ticker,
                        side="YES",
                        price=int(sell_px),
                        size=PER_ORDER_SIZE,
                        order_type="LIMIT",
                        tif="GTC",
                    )
                    oid = r.get("order", {}).get("order_id")
                    if oid: my_orders[oid] = r["order"]
                    print(f"[quote] SELL YES {PER_ORDER_SIZE}@{sell_px}")
                except Exception as e:
                    print(f"[sell error] {e}")

            # (Optional) fetch fills to update realized PnL if the API provides it
            # Here we just print inventory & stub PnL
            print(f"    inv={risk.net_yes} | BP={buying_power}¢ | last_top: yes_bid={q.yes_bid} yes_ask={q.yes_ask}")

            time.sleep(POLL_SEC)

        except KeyboardInterrupt:
            print("\n[!] Ctrl-C received. Attempting to cancel working orders...")
            try:
                w = client.list_orders(ticker=ticker, status="working")
                for o in w.get("orders", []):
                    oid = o.get("order_id")
                    if oid:
                        client.cancel_order(oid)
            except Exception as e:
                print(f"[cancel on exit warn] {e}")
            break

        except requests.HTTPError as he:
            # Show server response for easier debugging
            try:
                print(f"[HTTPError] {he.response.status_code} {he.response.text}")
            except Exception:
                print(f"[HTTPError] {he}")
            time.sleep(2.0)

        except Exception as e:
            print(f"[loop error] {type(e).__name__}: {e}")
            time.sleep(2.0)

if __name__ == "__main__":
    main()

