class RiskManager:
    """
    Simple risk layer: checks inventory, PnL, exposure.
    """

    def __init__(self, max_inventory=20, pnl_stop_cents=-3000):
        self.max_inventory = max_inventory
        self.pnl_stop_cents = pnl_stop_cents
        self.net_yes = 0
        self.realized_pnl = 0

    def update_position(self, net_yes, pnl):
        self.net_yes = net_yes
        self.realized_pnl = pnl

    def allow(self, order_intent):
        # inventory check
        if order_intent.action == "BUY" and self.net_yes >= self.max_inventory:
            return False
        if order_intent.action == "SELL" and self.net_yes <= -self.max_inventory:
            return False
        # PnL stop
        if self.realized_pnl <= self.pnl_stop_cents:
            return False
        return True

