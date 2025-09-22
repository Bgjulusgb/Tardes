import os
import logging
from typing import Dict, Optional

try:
    from alpaca_trade_api import REST
except Exception:  # pragma: no cover - optional dependency
    REST = None  # type: ignore


logger = logging.getLogger(__name__)


_api: Optional["REST"] = None


def _get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def get_api() -> Optional["REST"]:
    global _api
    if _api is not None:
        return _api
    if REST is None:
        logger.warning("alpaca_trade_api nicht installiert. Broker ist deaktiviert.")
        return None
    api_key = _get_env("ALPACA_API_KEY", "")
    api_secret = _get_env("ALPACA_API_SECRET", "")
    base_url = _get_env("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    if not api_key or not api_secret:
        logger.warning("ALPACA_API_KEY/ALPACA_API_SECRET fehlen. Broker ist deaktiviert.")
        return None
    _api = REST(api_key, api_secret, base_url, api_version="v2")
    return _api


def to_alpaca_symbol(symbol: str) -> str:
    # Convert yfinance style to Alpaca style for crypto
    if symbol.upper().endswith("-USD"):
        return symbol.upper().replace("-", "").replace("/", "")
    return symbol.upper()


def submit_order(signal: Dict) -> bool:
    api = get_api()
    if api is None:
        return False

    try:
        symbol = to_alpaca_symbol(signal.get("symbol", ""))
        side = "buy" if signal.get("action") == "BUY" else ("sell" if signal.get("action") == "SELL" else None)
        qty = int(signal.get("quantity") or 0)
        if side is None or qty <= 0:
            logger.info(f"Kein Trade ausgeführt für {symbol} (side={side}, qty={qty}).")
            return False

        api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type="market",
            time_in_force="gtc",
        )
        logger.info(f"Order ausgeführt: {side.upper()} {qty} {symbol}")
        return True
    except Exception as exc:
        logger.exception(f"Order fehlgeschlagen: {exc}")
        return False

