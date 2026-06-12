#!/usr/bin/env python3
"""
cli.py — CLI entry point for the Binance Futures Testnet trading bot.

Usage examples:
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 2500
  python cli.py --symbol BTCUSDT --side BUY --type STOP --quantity 0.001 --price 58000 --stop-price 57000
  python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 55000
  python cli.py --interactive
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv

from bot.client import BinanceClient, BinanceAPIError, BinanceNetworkError
from bot.logging_config import setup_logger
from bot.orders import dispatch_order
from bot.validators import (
    ValidationError,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

load_dotenv()
logger = setup_logger("trading_bot.cli")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════╗
║      Binance Futures Testnet — Trading Bot       ║
╚══════════════════════════════════════════════════╝
"""


def _load_credentials() -> tuple[str, str]:
    """Load API key and secret from environment variables."""
    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print(
            "\n[ERROR] Missing API credentials.\n"
            "  Set BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET\n"
            "  in your environment or in a .env file.\n"
        )
        logger.error("Missing API credentials in environment.")
        sys.exit(1)

    return api_key, api_secret


def _prompt(label: str, hint: str = "") -> str:
    """Prompt the user for input, showing an optional hint."""
    hint_str = f" ({hint})" if hint else ""
    return input(f"  {label}{hint_str}: ").strip()


def _run_interactive_mode() -> None:
    """
    Enhanced interactive CLI (Bonus).
    Walks the user through placing an order with prompts and inline validation.
    """
    print(BANNER)
    print("  Interactive mode — press Ctrl+C to quit at any time.\n")

    # -- Credentials --
    api_key, api_secret = _load_credentials()
    client = BinanceClient(api_key, api_secret)

    # Connectivity check
    try:
        server_time = client.get_server_time()
        print(f"  ✅  Connected to Binance Futures Testnet (server time: {server_time})\n")
    except Exception as exc:
        print(f"  ❌  Could not reach Binance Testnet: {exc}")
        logger.error("Connectivity check failed: %s", exc)
        sys.exit(1)

    # -- Gather inputs with validation loops --
    symbol = _validated_input("Symbol", validate_symbol, "e.g. BTCUSDT")
    side = _validated_input("Side", validate_side, "BUY / SELL")
    order_type = _validated_input(
        "Order type", validate_order_type, "MARKET / LIMIT / STOP / STOP_MARKET"
    )
    quantity_raw = _validated_input("Quantity", lambda x: str(validate_quantity(x)), "e.g. 0.001")
    quantity = Decimal(quantity_raw)

    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None

    if order_type in ("LIMIT", "STOP"):
        price_raw = _validated_input(
            "Limit price", lambda x: str(validate_price(x, order_type)), "e.g. 60000"
        )
        price = Decimal(price_raw)

    if order_type in ("STOP", "STOP_MARKET"):
        sp_raw = _validated_input(
            "Stop/trigger price", lambda x: str(validate_stop_price(x, order_type)), "e.g. 59500"
        )
        stop_price = Decimal(sp_raw)

    _execute_order(client, symbol, side, order_type, quantity, price, stop_price)


def _validated_input(label: str, validator, hint: str = "") -> str:
    """Loop until the user supplies a value that passes `validator`."""
    while True:
        raw = _prompt(label, hint)
        try:
            return validator(raw)
        except (ValidationError, ValueError) as exc:
            print(f"    ⚠️  {exc}")


def _execute_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal],
    stop_price: Optional[Decimal],
) -> None:
    """Send the order and print the result; handle all known exceptions."""
    print("\n  Sending order to Binance Futures Testnet …\n")
    logger.info(
        "Executing order: symbol=%s side=%s type=%s qty=%s price=%s stopPrice=%s",
        symbol, side, order_type, quantity, price, stop_price,
    )
    try:
        result = dispatch_order(
            client=client,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
        print(result.display())
        logger.info("Order completed successfully. orderId=%s status=%s", result.order_id, result.status)
        print("\n  ✅  Success!\n")

    except ValidationError as exc:
        print(f"\n  ❌  Validation error: {exc}\n")
        logger.warning("Validation error: %s", exc)
        sys.exit(2)

    except BinanceAPIError as exc:
        print(f"\n  ❌  Binance API error [{exc.code}]: {exc.message}\n")
        logger.error("BinanceAPIError: code=%d msg=%s", exc.code, exc.message)
        sys.exit(3)

    except BinanceNetworkError as exc:
        print(f"\n  ❌  Network error: {exc}\n")
        logger.error("BinanceNetworkError: %s", exc)
        sys.exit(4)

    except Exception as exc:
        print(f"\n  ❌  Unexpected error: {exc}\n")
        logger.exception("Unexpected error during order execution")
        sys.exit(5)


# ─────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet — CLI Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Market BUY
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

  # Limit SELL
  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 2500

  # Stop-Limit BUY (bonus)
  python cli.py --symbol BTCUSDT --side BUY --type STOP --quantity 0.001 --price 58000 --stop-price 57500

  # Stop-Market SELL (bonus)
  python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 55000

  # Interactive mode (bonus)
  python cli.py --interactive
        """,
    )

    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Launch guided interactive mode",
    )
    parser.add_argument("--symbol", "-s", type=str, help="Trading pair (e.g., BTCUSDT)")
    parser.add_argument("--side", type=str, help="BUY or SELL")
    parser.add_argument(
        "--type", dest="order_type", type=str,
        help="Order type: MARKET | LIMIT | STOP | STOP_MARKET",
    )
    parser.add_argument("--quantity", "-q", type=str, help="Order quantity")
    parser.add_argument("--price", "-p", type=str, default=None, help="Limit price (required for LIMIT/STOP)")
    parser.add_argument("--stop-price", type=str, default=None, dest="stop_price",
                        help="Stop/trigger price (required for STOP/STOP_MARKET)")
    parser.add_argument(
        "--tif", type=str, default="GTC", dest="time_in_force",
        choices=["GTC", "IOC", "FOK"],
        help="Time-in-force for LIMIT orders (default: GTC)",
    )
    return parser


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(BANNER)

    # Interactive mode
    if args.interactive:
        _run_interactive_mode()
        return

    # Non-interactive: all required args must be present
    missing = [f for f in ("symbol", "side", "order_type", "quantity") if not getattr(args, f)]
    if missing:
        parser.print_help()
        print(f"\n  ❌  Missing required arguments: {', '.join(missing)}\n")
        sys.exit(1)

    # Validate inputs
    try:
        symbol = validate_symbol(args.symbol)
        side = validate_side(args.side)
        order_type = validate_order_type(args.order_type)
        quantity = validate_quantity(args.quantity)
        price = validate_price(args.price, order_type)
        stop_price = validate_stop_price(args.stop_price, order_type)
    except ValidationError as exc:
        print(f"\n  ❌  {exc}\n")
        logger.warning("CLI validation error: %s", exc)
        sys.exit(2)

    # Build client
    api_key, api_secret = _load_credentials()
    client = BinanceClient(api_key, api_secret)

    # Connectivity check
    try:
        client.get_server_time()
        logger.info("Connectivity check passed.")
    except BinanceNetworkError as exc:
        print(f"\n  ❌  Cannot reach Binance Testnet: {exc}\n")
        logger.error("Connectivity check failed: %s", exc)
        sys.exit(4)

    _execute_order(client, symbol, side, order_type, quantity, price, stop_price)


if __name__ == "__main__":
    main()
