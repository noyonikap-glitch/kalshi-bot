from dataclasses import dataclass

@dataclass
class OrderIntent:
    action: str   # "BUY" or "SELL"
    side: str     # "YES" or "NO"
    price: int    # in cents
    size: int     # number of contracts

class ExecutionEngine:
    """
    Turns strategy intents into live orders.
    """

    def __init__(self, client, ticker, risk_mgr):
        self.client = client
        self.ticker = ticker
        self.risk_mgr = risk_mgr

    def execute(self, intents):
        placed_orders = []
        for intent in intents:
            if not self.risk_mgr.allow(intent):
                continue
            payload = {
                "action": intent.action,
                "ticker": self.ticker,
                "type": "LIMIT",
                "time_in_force": "GTC",
                "side": intent.side,
                "price": intent.price,
                "size": intent.size,
            }
            try:
                res = self.client.place_order(**payload)
                placed_orders.append(res)
            except Exception as e:
                print(f"[execution error] {e}")
        return placed_orders

