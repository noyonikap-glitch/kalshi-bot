from ..strat_base import Strategy
from ..execution import OrderIntent
from ..data import mid_price, parse_orderbook

class MarketMaker(Strategy):
    def __init__(self, spread=4, size=1):
        self.spread = spread
        self.size = size

    def on_book(self, orderbook, positions, account):
        book = parse_orderbook(orderbook)
        mid = mid_price(book)
        if mid is None:
            return []
        buy_px = max(1, int(mid - self.spread/2))
        sell_px = min(99, int(mid + self.spread/2))
        return [
            OrderIntent("BUY", "YES", buy_px, self.size),
            OrderIntent("SELL", "YES", sell_px, self.size),
        ]

