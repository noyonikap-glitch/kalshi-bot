from ..strat_base import Strategy
from ..execution import OrderIntent
from ..data import mid_price, parse_orderbook

class Momentum(Strategy):
    """
    Naive momentum: if mid is trending up, buy YES; if trending down, sell YES.
    """

    def __init__(self, size=1):
        self.size = size
        self.last_mid = None

    def on_book(self, orderbook, positions, account):
        book = parse_orderbook(orderbook)
        mid = mid_price(book)
        if mid is None or self.last_mid is None:
            self.last_mid = mid
            return []

        intents = []
        if mid > self.last_mid:
            intents.append(OrderIntent("BUY", "YES", int(mid), self.size))
        elif mid < self.last_mid:
            intents.append(OrderIntent("SELL", "YES", int(mid), self.size))

        self.last_mid = mid
        return intents

