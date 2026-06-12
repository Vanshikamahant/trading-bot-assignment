"""
Input validation for trading bot CLI arguments.
Validates symbol, side, order type, quantity, and price before any API calls.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from bot.logging_config import setup_logger

logger = setup_logger("trading_bot.validators")

# --- Constants ---
VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP"}  # STOP = Stop-Limit (bonus)
SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}USDT$")


class ValidationError(ValueError):
    """Raised when user-supplied input fails validation."""
    pass


def validate_symbol(symbol: str) -> str:
    """
    Validate and normalise a trading symbol (e.g., 'btcusdt' → 'BTCUSDT').

    Args:
        symbol: Raw symbol string from CLI

    Returns:
        Uppercased, validated symbol

    Raises:
        ValidationError: If the symbol does not match expected format
    """
    normalised = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(normalised):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. Expected format: <ASSET>USDT (e.g., BTCUSDT, ETHUSDT)."
        )
    logger.debug("Symbol validated: %s", normalised)
    return normalised


def validate_side(side: str) -> str:
    """
    Validate order side.

    Args:
        side: 'BUY' or 'SELL' (case-insensitive)

    Returns:
        Uppercased side string

    Raises:
        ValidationError: If side is not BUY or SELL
    """
    normalised = side.strip().upper()
    if normalised not in VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    logger.debug("Side validated: %s", normalised)
    return normalised


def validate_order_type(order_type: str) -> str:
    """
    Validate order type.

    Args:
        order_type: 'MARKET', 'LIMIT', or 'STOP_MARKET' (case-insensitive)

    Returns:
        Uppercased order type

    Raises:
        ValidationError: If order type is not supported
    """
    normalised = order_type.strip().upper()
    if normalised not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    logger.debug("Order type validated: %s", normalised)
    return normalised


def validate_quantity(quantity: str | float) -> Decimal:
    """
    Validate order quantity.

    Args:
        quantity: Quantity as string or float

    Returns:
        Positive Decimal quantity

    Raises:
        ValidationError: If quantity is invalid or non-positive
    """
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValidationError(f"Invalid quantity '{quantity}'. Must be a positive number.")

    if qty <= 0:
        raise ValidationError(f"Quantity must be greater than zero, got '{quantity}'.")

    logger.debug("Quantity validated: %s", qty)
    return qty


def validate_price(price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """
    Validate order price (required for LIMIT/STOP orders, ignored for MARKET).

    Args:
        price: Price as string or float (may be None for MARKET)
        order_type: Already-validated order type string

    Returns:
        Positive Decimal price, or None for MARKET orders

    Raises:
        ValidationError: If price is required but missing/invalid
    """
    requires_price = {"LIMIT", "STOP"}

    if order_type in requires_price:
        if price is None:
            raise ValidationError(
                f"Price is required for {order_type} orders. Use --price <value>."
            )
        try:
            p = Decimal(str(price))
        except InvalidOperation:
            raise ValidationError(f"Invalid price '{price}'. Must be a positive number.")

        if p <= 0:
            raise ValidationError(f"Price must be greater than zero, got '{price}'.")

        logger.debug("Price validated: %s", p)
        return p

    # MARKET / STOP_MARKET — price is irrelevant
    if price is not None:
        logger.debug("Price '%s' provided for %s order — will be ignored.", price, order_type)
    return None


def validate_stop_price(stop_price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """
    Validate stop price for STOP / STOP_MARKET orders.

    Args:
        stop_price: Stop-trigger price
        order_type: Already-validated order type

    Returns:
        Positive Decimal stop price, or None

    Raises:
        ValidationError: If stop price is required but missing/invalid
    """
    stop_types = {"STOP", "STOP_MARKET"}

    if order_type in stop_types:
        if stop_price is None:
            raise ValidationError(
                f"--stop-price is required for {order_type} orders."
            )
        try:
            sp = Decimal(str(stop_price))
        except InvalidOperation:
            raise ValidationError(f"Invalid stop price '{stop_price}'. Must be a positive number.")

        if sp <= 0:
            raise ValidationError(f"Stop price must be greater than zero, got '{stop_price}'.")

        logger.debug("Stop price validated: %s", sp)
        return sp

    return None
