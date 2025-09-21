from abc import ABC, abstractmethod

class Strategy(ABC):
    """
    Base strategy interface.
    """

    @abstractmethod
    def on_book(self, orderbook, positions, account):
        """
        Given market state, return a list of OrderIntents.
        """
        pass

