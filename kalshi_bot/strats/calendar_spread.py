from ..strat_base import Strategy
from ..execution import OrderIntent

class CalendarSpread(Strategy):
    """
    Example: long one contract in one market, short in a related future market.
    Placeholder for real logic.
    """

    def __init__(self, size=1):
        self.size = size

    def on_book(self, orderbook, positions, account):
        # TODO: implement cross-market logic
        # For now, just returns no orders.
        return []

