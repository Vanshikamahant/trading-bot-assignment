"""
Binance Futures Testnet REST client wrapper.
Handles authentication (HMAC-SHA256), request signing, and HTTP communication.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests

from bot.logging_config import setup_logger

logger = setup_logger("trading_bot.client")

# BASE_URL = "https://testnet.binancefuture.com"
BASE_URL = "https://demo-fapi.binance.com"
RECV_WINDOW = 5000  # milliseconds


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceNetworkError(ConnectionError):
    """Raised on network-level failures (timeouts, DNS, etc.)."""
    pass


class BinanceClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    Args:
        api_key: Testnet API key
        api_secret: Testnet API secret
        base_url: Override the default testnet base URL (useful for tests)
        timeout: HTTP request timeout in seconds
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
        timeout: int = 10,
    ):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "TradingBot/1.0",
            }
        )
        logger.info("BinanceClient initialised (base_url=%s)", self._base_url)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _timestamp(self) -> int:
        """Return current UTC timestamp in milliseconds."""
        return int(time.time() * 1000)

    def _sign(self, query_string: str) -> str:
        """Generate HMAC-SHA256 signature for the given query string."""
        return hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _build_signed_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp and signature to a parameter dict (in-place copy)."""
        signed = dict(params)
        signed["timestamp"] = self._timestamp()
        signed["recvWindow"] = RECV_WINDOW
        query_string = urllib.parse.urlencode(signed)
        signed["signature"] = self._sign(query_string)
        return signed

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request against the Binance API.

        Args:
            method: HTTP method ('GET', 'POST', 'DELETE')
            endpoint: API path (e.g., '/fapi/v1/order')
            params: Query / body parameters
            signed: Whether to add timestamp + signature

        Returns:
            Parsed JSON response dict

        Raises:
            BinanceAPIError: On API-level errors
            BinanceNetworkError: On network failures
        """
        url = f"{self._base_url}{endpoint}"
        payload = params or {}

        if signed:
            payload = self._build_signed_params(payload)

        # Log the outgoing request (mask secret in logs)
        logger.debug(
            "REQUEST  %s %s | params=%s",
            method,
            endpoint,
            {k: v for k, v in payload.items() if k != "signature"},
        )

        try:
            if method == "GET":
                response = self._session.get(url, params=payload, timeout=self._timeout)
            elif method == "POST":
                response = self._session.post(url, data=payload, timeout=self._timeout)
            elif method == "DELETE":
                response = self._session.delete(url, params=payload, timeout=self._timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s %s", method, endpoint)
            raise BinanceNetworkError(f"Request timed out ({method} {endpoint})") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s %s | %s", method, endpoint, exc)
            raise BinanceNetworkError(f"Connection error ({method} {endpoint}): {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected request error: %s", exc)
            raise BinanceNetworkError(f"Request failed: {exc}") from exc

        logger.debug(
            "RESPONSE %s %s | status=%d | body=%s",
            method,
            endpoint,
            response.status_code,
            response.text[:500],  # truncate large responses in logs
        )

        try:
            data: Dict[str, Any] = response.json()
        except ValueError:
            logger.error("Non-JSON response: %s", response.text[:200])
            raise BinanceAPIError(-1, f"Non-JSON response: {response.text[:200]}")

        # Binance returns error as {"code": <negative>, "msg": "..."}
        if isinstance(data, dict) and data.get("code", 0) < 0:
            code = data["code"]
            msg = data.get("msg", "Unknown error")
            logger.error("API error code=%d msg=%s", code, msg)
            raise BinanceAPIError(code, msg)

        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds."""
        data = self._request("GET", "/fapi/v1/time")
        return data["serverTime"]

    def get_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange info (symbols, filters, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_account(self) -> Dict[str, Any]:
        """Fetch account information (balances, positions)."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def place_order(self, **order_params: Any) -> Dict[str, Any]:
        """
        Place a new futures order.

        Keyword Args:
            symbol (str): e.g., 'BTCUSDT'
            side (str): 'BUY' or 'SELL'
            type (str): 'MARKET', 'LIMIT', 'STOP_MARKET', 'STOP'
            quantity (str|float): Order quantity
            price (str|float, optional): Required for LIMIT / STOP
            stopPrice (str|float, optional): Required for STOP / STOP_MARKET
            timeInForce (str, optional): 'GTC', 'IOC', 'FOK' (required for LIMIT)

        Returns:
            Order response dict from Binance

        Raises:
            BinanceAPIError: On API-level rejection
            BinanceNetworkError: On network failures
        """
        logger.info(
            "Placing order: symbol=%s side=%s type=%s qty=%s price=%s stopPrice=%s",
            order_params.get("symbol"),
            order_params.get("side"),
            order_params.get("type"),
            order_params.get("quantity"),
            order_params.get("price", "N/A"),
            order_params.get("stopPrice", "N/A"),
        )
        response = self._request("POST", "/fapi/v1/order", params=order_params, signed=True)
        logger.info(
            "Order placed: orderId=%s status=%s executedQty=%s",
            response.get("orderId"),
            response.get("status"),
            response.get("executedQty"),
        )
        return response

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an existing open order."""
        return self._request(
            "DELETE",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Query a specific order by ID."""
        return self._request(
            "GET",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """List all open orders, optionally filtered by symbol."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params=params, signed=True)
