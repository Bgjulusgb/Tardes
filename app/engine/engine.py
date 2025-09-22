import os
import logging
from typing import Dict, List

import pandas as pd
import yfinance as yf

from .strategies import analyze_symbol, merge_signals


logger = logging.getLogger(__name__)


def get_env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    return value


def get_config() -> Dict:
    symbols_env = get_env("SYMBOLS", "AAPL,MSFT,BTC-USD,ETH-USD")
    symbols = [s.strip() for s in symbols_env.split(",") if s.strip()]
    equity = float(get_env("ACCOUNT_EQUITY", "10000"))
    risk_pct = float(get_env("RISK_PER_TRADE_PCT", "1.0"))
    period = get_env("YF_PERIOD", "6mo")
    interval = get_env("YF_INTERVAL", "1d")
    timeframe = interval
    auto_trade = get_env("AUTO_TRADE", "false").lower() in ("1", "true", "yes")
    return {
        "symbols": symbols,
        "equity": equity,
        "risk_pct": risk_pct,
        "period": period,
        "interval": interval,
        "timeframe": timeframe,
        "auto_trade": auto_trade,
    }


def fetch_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    try:
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False)
        if not isinstance(df, pd.DataFrame) or df.empty:
            logger.warning(f"Keine Daten für {symbol} erhalten.")
            return pd.DataFrame()
        df = df.rename(columns={c: c.title() for c in df.columns})
        return df
    except Exception as exc:
        logger.exception(f"Fehler beim Laden der Daten für {symbol}: {exc}")
        return pd.DataFrame()


def run_analysis(symbols: List[str], equity: float, risk_pct: float, period: str, interval: str, timeframe: str) -> List[Dict]:
    signals: List[Dict] = []
    for symbol in symbols:
        df = fetch_history(symbol, period, interval)
        signal = analyze_symbol(symbol=symbol, data=df, equity=equity, risk_per_trade_pct=risk_pct, timeframe=timeframe)
        signals.append(signal)
    return merge_signals(signals)

