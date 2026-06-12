# Binance Futures Testnet — Trading Bot

A clean, production-style Python CLI bot for placing orders on the **Binance Futures USDT-M Testnet**.

---

## Features

| Feature | Details |
|---|---|
| Order types | MARKET, LIMIT, **STOP-LIMIT** (bonus), **STOP_MARKET** (bonus) |
| Sides | BUY and SELL |
| CLI | `argparse`-based with full validation, plus `--interactive` guided mode (bonus) |
| Logging | Rotating file log + console, structured formatting |
| Error handling | API errors, network failures, invalid inputs — all caught and reported clearly |
| Structure | Layered: `client.py` → `orders.py` → `cli.py`; validators in their own module |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py         # Binance REST client (auth, signing, HTTP)
│   ├── orders.py         # Order placement logic + OrderResult display
│   ├── validators.py     # Input validation (symbol, side, type, qty, price)
│   └── logging_config.py # Rotating file + console logging setup
├── logs/
│   ├── market_order.log
│   └── limit_order.log
├── cli.py                # CLI entry point (argparse + interactive mode)
├── .env          # Environment variable template
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet Credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in (or create an account — GitHub login works)
3. Go to **API Management** → generate a new key pair
4. Copy your **API Key** and **Secret Key**

### 2. Clone / Unzip & Install Dependencies

```bash
cd trading_bot
pip install -r requirements.txt
```

### 3. Configure Credentials

```bash
cp .env.example .env
```

Edit `.env`:

```
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_API_SECRET=your_api_secret_here
```

> The bot reads these at startup via `python-dotenv`.

---

## How to Run

### Place a MARKET order

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Place a LIMIT order

```bash
python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 2500
```

### Place a Stop-Limit order (bonus)

```bash
python cli.py --symbol BTCUSDT --side BUY --type STOP --quantity 0.001 \
              --price 58000 --stop-price 57500
```

### Place a Stop-Market order (bonus)

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET \
              --quantity 0.001 --stop-price 55000
```

### Interactive guided mode (bonus)

```bash
python cli.py --interactive
```

Prompts for each field with inline validation — great for manual testing.

### See all options

```bash
python cli.py --help
```

---

## Example Output

```
╔══════════════════════════════════════════════════╗
║      Binance Futures Testnet — Trading Bot       ║
╚══════════════════════════════════════════════════╝

  Sending order to Binance Futures Testnet …

─────────────────────────────────────────────────────
  ORDER REQUEST SUMMARY
─────────────────────────────────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001
─────────────────────────────────────────────────────

═══════════════════════════════════════════════════════
  ORDER RESULT
═══════════════════════════════════════════════════════
  Order ID       : 4751937267
  Client Order ID: mBr2hFOtYtnbNlYJSeBdp2
  Symbol         : BTCUSDT
  Side           : BUY
  Type           : MARKET
  Status         : FILLED
  Orig Quantity  : 0.001
  Executed Qty   : 0.001
  Avg Fill Price : 96245.10
═══════════════════════════════════════════════════════
  ✅  Order FILLED successfully.
═══════════════════════════════════════════════════════

  ✅  Success!
```

---

## Logging

All activity is logged to `logs/trading_bot.log` (rotating, max 5 MB × 3 backups).

Log levels:
- **DEBUG** (file only) — full request/response payloads, validated values
- **INFO** (file + console) — order submissions, results, connectivity checks
- **WARNING/ERROR** (file + console) — validation failures, API errors, network issues

Sample log files for a MARKET and LIMIT order are included in `logs/`.

---

## Assumptions

1. **USDT-M Futures only** — symbol validation requires `<ASSET>USDT` format.
2. **Testnet leverage/margin** — the testnet pre-funds accounts; no real collateral needed.
3. **Quantity precision** — the bot passes quantity as-is. If Binance rejects due to LOT_SIZE filters, adjust the quantity to match the symbol's step size (visible in `GET /fapi/v1/exchangeInfo`).
4. **Credentials via environment** — API key/secret are never hardcoded; they must be set in `.env` or shell environment.
5. **Python 3.9+** required (uses `from __future__ import annotations`).

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP client for Binance REST API |
| `python-dotenv` | Loads `.env` credential file |

No Binance SDK used — pure REST calls for transparency and minimal dependencies.
