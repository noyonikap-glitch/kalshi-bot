import os
import time
import argparse
from dotenv import load_dotenv

from kalshi_bot.client import KalshiClient
from kalshi_bot.risk import RiskManager
from kalshi_bot.execution import ExecutionEngine
from kalshi_bot.utils import log_to_csv, timestamp

# import strategies
from kalshi_bot.strats.market_maker import MarketMaker
from kalshi_bot.strats.momentum import Momentum
from kalshi_bot.strats.calendar_spread import CalendarSpread

STRAT_MAP = {
    "market_maker": MarketMaker,
    "momentum": Momentum,
    "calendar_spread": CalendarSpread,
}

def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True, help="Market ticker to trade")
    parser.add_argument("--strategy", choices=STRAT_MAP.keys(), default="market_maker")
    parser.add_argument("--spread", type=int, default=4, help="Spread for market maker")
    parser.add_argument("--size", type=int, default=1, help="Order size")
    args = parser.parse_args()

    # --- Init layers ---
    client = KalshiClient()
    client.login()
    me = client.me()
    print(f"[*] Logged in as {me.get('member', {}).get('email')}")

    risk_mgr = RiskManager(max_inventory=20, pnl_stop_cents=-3000)
    strat_cls = STRAT_MAP[args.strategy]
    if args.strategy == "market_maker":
        strat = strat_cls(spread=args.spread, size=args.size)
    else:
        strat = strat_cls(size=args.size)

    engine = ExecutionEngine(client, args.ticker, risk_mgr)

    print(f"[*] Running {args.strategy} on {args.ticker}...")

    # --- Main loop ---
    while True:
        try:
            ob = client.get_orderbook(args.ticker)
            acct = client.account()
            pos = client.list_positions()

            intents = strat.on_book(ob, pos, acct)
            placed = engine.execute(intents)

            for order in placed:
                order_data = order.get("order", {})
                row = {
                    "ts": timestamp(),
                    "ticker": args.ticker,
                    "strategy": args.strategy,
                    "action": order_data.get("action"),
                    "side": order_data.get("side"),
                    "price": order_data.get("price"),
                    "size": order_data.get("size"),
                }
                log_to_csv("logs/trades.csv", row, list(row.keys()))

            time.sleep(2.0)  # poll frequency
        except KeyboardInterrupt:
            print("\n[!] Stopping bot...")
            break
        except Exception as e:
            print(f"[loop error] {type(e).__name__}: {e}")
            time.sleep(2.0)

if __name__ == "__main__":
    main()

