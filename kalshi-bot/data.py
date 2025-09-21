from dataclasses import dataclass

@dataclass
class BookQuote:
    yes_bid: int | None
    yes_ask: int | None
    no_bid: int | None
    no_ask: int | None

def parse_orderbook(orderbook: dict) -> BookQuote:
    yes_bids = orderbook.get("yes", {}).get("bids", [])
    yes_asks = orderbook.get("yes", {}).get("asks", [])
    no_bids  = orderbook.get("no",  {}).get("bids", [])
    no_asks  = orderbook.get("no",  {}).get("asks", [])

    return BookQuote(
        yes_bid=yes_bids[0][0] if yes_bids else None,
        yes_ask=yes_asks[0][0] if yes_asks else None,
        no_bid=no_bids[0][0] if no_bids else None,
        no_ask=no_asks[0][0] if no_asks else None,
    )

def mid_price(book: BookQuote) -> float | None:
    if book.yes_bid and book.yes_ask:
        return (book.yes_bid + book.yes_ask) / 2.0
    if book.yes_bid:
        return float(book.yes_bid)
    if book.yes_ask:
        return float(book.yes_ask)
    return None

