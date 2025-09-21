import os
import requests
import backoff

class KalshiClient:
    """
    Thin REST wrapper around Kalshi Trade API v2.
    """

    def __init__(self, base_url=None, email=None, password=None):
        self.base_url = base_url or os.getenv("KALSHI_BASE_URL", "https://demo-api.kalshi.co/trade-api/v2")
        self.email = email or os.getenv("KALSHI_EMAIL")
        self.password = password or os.getenv("KALSHI_PASSWORD")
        self.s = requests.Session()
        self.s.headers.update({"Content-Type": "application/json"})

    @backoff.on_exception(backoff.expo, (requests.RequestException,), max_time=60)
    def _req(self, method, path, **kw):
        url = f"{self.base_url}{path}"
        r = self.s.request(method, url, timeout=15, **kw)
        if r.status_code == 401:
            self.login()
            r = self.s.request(method, url, timeout=15, **kw)
        r.raise_for_status()
        return r.json() if r.text.strip() else {}

    def login(self):
        payload = {"email": self.email, "password": self.password}
        res = self._req("POST", "/login", json=payload)
        return res

    # --- Common endpoints ---
    def me(self):
        return self._req("GET", "/members/self")

    def account(self):
        return self._req("GET", "/accounts/self")

    def get_markets(self, params=None):
        return self._req("GET", "/markets", params=params or {})

    def get_market(self, ticker):
        return self._req("GET", f"/markets/{ticker}")

    def get_orderbook(self, ticker):
        return self._req("GET", f"/markets/{ticker}/orderbook")

    def place_order(self, **payload):
        return self._req("POST", "/orders", json=payload)

    def cancel_order(self, order_id):
        return self._req("DELETE", f"/orders/{order_id}")

    def list_orders(self, params=None):
        return self._req("GET", "/orders", params=params or {})

    def list_positions(self):
        return self._req("GET", "/positions")

