"""
Order placement logic.
Translates validated CLI inputs into Binance API calls via BinanceClient.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from bot.client import BinanceClient, BinanceAPIError, BinanceNetworkError
from bot.logging_config import setup_logger

logger = setup_logger("trading_bot.orders")


class OrderResult:
    """
    Wraps a raw Binance order response for clean display and access.
    """

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.order_id: int = raw.get("orderId", 0)
        self.symbol: str = raw.get("symbol", "")
        self.side: str = raw.get("side", "")
        self.order_type: str = raw.get("type", "")
        self.status: str = raw.get("status", "")
        self.orig_qty: str = raw.get("origQty", "")
        self.executed_qty: str = raw.get("executedQty", "")
        self.avg_price: str = raw.get("avgPrice", "")
        self.price: str = raw.get("price", "0")
        self.stop_price: str = raw.get("stopPrice", "0")
        self.time_in_force: str = raw.get("timeInForce", "")
        self.client_order_id: str = raw.get("clientOrderId", "")
        self.update_time: int = raw.get("updateTime", 0)

    def is_filled(self) -> bool:
        return self.status == "FILLED"

    def is_open(self) -> bool:
        return self.status in ("NEW", "PARTIALLY_FILLED")

    def display(self) -> str:
        """Return a human-readable summary of the order result."""
        lines = [
            "",
            "═" * 55,
            "  ORDER RESULT",
            "═" * 55,
            f"  Order ID       : {self.order_id}",
            f"  Client Order ID: {self.client_order_id}",
            f"  Symbol         : {self.symbol}",
            f"  Side           : {self.side}",
            f"  Type           : {self.order_type}",
            f"  Status         : {self.status}",
            f"  Orig Quantity  : {self.orig_qty}",
            f"  Executed Qty   : {self.executed_qty}",
        ]
        if self.avg_price and self.avg_price != "0":
            lines.append(f"  Avg Fill Price : {self.avg_price}")
        if self.price and self.price != "0":
            lines.append(f"  Limit Price    : {self.price}")
        if self.stop_price and self.stop_price != "0":
            lines.append(f"  Stop Price     : {self.stop_price}")
        if self.time_in_force:
            lines.append(f"  Time in Force  : {self.time_in_force}")
        lines.append("═" * 55)
        if self.is_filled():
            lines.append("  ✅  Order FILLED successfully.")
        elif self.is_open():
            lines.append("  📋  Order is OPEN / pending fill.")
        else:
            lines.append(f"  ℹ️   Order status: {self.status}")
        lines.append("═" * 55)
        return "\n".join(lines)


def _summary_header(
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
) -> str:
    """Render a pre-flight order summary for the user."""
    lines = [
        "",
        "─" * 55,
        "  ORDER REQUEST SUMMARY",
        "─" * 55,
        f"  Symbol     : {symbol}",
        f"  Side       : {side}",
        f"  Type       : {order_type}",
        f"  Quantity   : {quantity}",
    ]
    if price is not None:
        lines.append(f"  Limit Price: {price}")
    if stop_price is not None:
        lines.append(f"  Stop Price : {stop_price}")
    lines.append("─" * 55)
    return "\n".join(lines)


def place_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
) -> OrderResult:
    """
    Place a MARKET order.

    Args:
        client: Authenticated BinanceClient instance
        symbol: e.g., 'BTCUSDT'
        side: 'BUY' or 'SELL'
        quantity: Order quantity

    Returns:
        OrderResult wrapping the API response

    Raises:
        BinanceAPIError / BinanceNetworkError on failure
    """
    print(_summary_header(symbol, side, "MARKET", quantity))
    logger.info("Submitting MARKET order: %s %s qty=%s", side, symbol, quantity)

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=str(quantity),
    )
    result = OrderResult(raw)
    logger.info("MARKET order response: %s", raw)
    return result


def place_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    time_in_force: str = "GTC",
) -> OrderResult:
    """
    Place a LIMIT order.

    Args:
        client: Authenticated BinanceClient instance
        symbol: e.g., 'BTCUSDT'
        side: 'BUY' or 'SELL'
        quantity: Order quantity
        price: Limit price
        time_in_force: 'GTC' (default), 'IOC', or 'FOK'

    Returns:
        OrderResult wrapping the API response
    """
    print(_summary_header(symbol, side, "LIMIT", quantity, price=price))
    logger.info(
        "Submitting LIMIT order: %s %s qty=%s price=%s tif=%s",
        side, symbol, quantity, price, time_in_force,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="LIMIT",
        quantity=str(quantity),
        price=str(price),
        timeInForce=time_in_force,
    )
    result = OrderResult(raw)
    logger.info("LIMIT order response: %s", raw)
    return result


def place_stop_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    stop_price: Decimal,
    time_in_force: str = "GTC",
) -> OrderResult:
    """
    Place a STOP (Stop-Limit) order. [Bonus order type]

    A Stop-Limit order triggers when the market reaches `stop_price`,
    then places a limit order at `price`.

    Args:
        client: Authenticated BinanceClient instance
        symbol: e.g., 'BTCUSDT'
        side: 'BUY' or 'SELL'
        quantity: Order quantity
        price: Limit price (filled at this price once triggered)
        stop_price: Trigger price
        time_in_force: 'GTC' (default)

    Returns:
        OrderResult wrapping the API response
    """
    print(_summary_header(symbol, side, "STOP (Stop-Limit)", quantity, price=price, stop_price=stop_price))
    logger.info(
        "Submitting STOP-LIMIT order: %s %s qty=%s price=%s stopPrice=%s tif=%s",
        side, symbol, quantity, price, stop_price, time_in_force,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="STOP",
        quantity=str(quantity),
        price=str(price),
        stopPrice=str(stop_price),
        timeInForce=time_in_force,
    )
    result = OrderResult(raw)
    logger.info("STOP-LIMIT order response: %s", raw)
    return result


def place_stop_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    stop_price: Decimal,
) -> OrderResult:
    """
    Place a STOP_MARKET order. [Bonus order type]

    Triggers a market order when `stop_price` is reached.

    Returns:
        OrderResult wrapping the API response
    """
    print(_summary_header(symbol, side, "STOP_MARKET", quantity, stop_price=stop_price))
    logger.info(
        "Submitting STOP_MARKET order: %s %s qty=%s stopPrice=%s",
        side, symbol, quantity, stop_price,
    )

    raw = client.place_order(
        symbol=symbol,
        side=side,
        type="STOP_MARKET",
        quantity=str(quantity),
        stopPrice=str(stop_price),
    )
    result = OrderResult(raw)
    logger.info("STOP_MARKET order response: %s", raw)
    return result


def dispatch_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    time_in_force: str = "GTC",
) -> OrderResult:
    """
    Route to the correct order function based on order_type.

    Args:
        client: Authenticated BinanceClient instance
        symbol: Trading pair
        side: BUY / SELL
        order_type: MARKET / LIMIT / STOP / STOP_MARKET
        quantity: Order quantity
        price: Limit price (LIMIT / STOP)
        stop_price: Trigger price (STOP / STOP_MARKET)
        time_in_force: GTC / IOC / FOK

    Returns:
        OrderResult
    """
    if order_type == "MARKET":
        return place_market_order(client, symbol, side, quantity)

    if order_type == "LIMIT":
        return place_limit_order(client, symbol, side, quantity, price, time_in_force)

    if order_type == "STOP":
        return place_stop_limit_order(client, symbol, side, quantity, price, stop_price, time_in_force)

    if order_type == "STOP_MARKET":
        return place_stop_market_order(client, symbol, side, quantity, stop_price)

    raise ValueError(f"Unsupported order type: {order_type}")
