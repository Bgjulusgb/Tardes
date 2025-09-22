import math
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _safe_pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b * 100.0


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period, min_periods=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(method="bfill").fillna(50.0)


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd = ema_fast - ema_slow
    signal_line = compute_ema(macd, signal)
    histogram = macd - signal_line
    return macd, signal_line, histogram


def compute_bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = compute_sma(close, window)
    rolling_std = close.rolling(window=window, min_periods=window).std()
    upper = sma + num_std * rolling_std
    lower = sma - num_std * rolling_std
    return lower, sma, upper


def compute_momentum(close: pd.Series, window: int = 10) -> pd.Series:
    return close / close.shift(window) - 1.0


def _strategy_rsi(close: pd.Series) -> str:
    rsi = compute_rsi(close)
    if len(rsi) < 2:
        return "HOLD"
    prev, curr = float(rsi.iloc[-2]), float(rsi.iloc[-1])
    if prev < 30 <= curr:
        return "BUY"
    if prev > 70 >= curr:
        return "SELL"
    # Overextended conditions as weaker signals
    if curr < 25:
        return "BUY"
    if curr > 75:
        return "SELL"
    return "HOLD"


def _strategy_macd(close: pd.Series) -> str:
    macd, signal, _ = compute_macd(close)
    if len(macd) < 2:
        return "HOLD"
    prev_cross = float(macd.iloc[-2] - signal.iloc[-2])
    curr_cross = float(macd.iloc[-1] - signal.iloc[-1])
    if prev_cross <= 0 < curr_cross:
        return "BUY"
    if prev_cross >= 0 > curr_cross:
        return "SELL"
    return "HOLD"


def _strategy_sma_crossover(close: pd.Series) -> str:
    sma_short = compute_sma(close, 50)
    sma_long = compute_sma(close, 200)
    if len(close) < 200:
        return "HOLD"
    prev_cross = float(sma_short.iloc[-2] - sma_long.iloc[-2])
    curr_cross = float(sma_short.iloc[-1] - sma_long.iloc[-1])
    if prev_cross <= 0 < curr_cross:
        return "BUY"
    if prev_cross >= 0 > curr_cross:
        return "SELL"
    return "HOLD"


def _strategy_bollinger(close: pd.Series) -> str:
    lower, mid, upper = compute_bollinger(close)
    if len(close) < 20:
        return "HOLD"
    price = float(close.iloc[-1])
    if price <= float(lower.iloc[-1]):
        return "BUY"
    if price >= float(upper.iloc[-1]):
        return "SELL"
    return "HOLD"


def _strategy_momentum(close: pd.Series) -> str:
    mom = compute_momentum(close, 10)
    if len(mom) < 11:
        return "HOLD"
    curr = float(mom.iloc[-1])
    # Use weak threshold to be responsive
    if curr > 0.01:
        return "BUY"
    if curr < -0.01:
        return "SELL"
    return "HOLD"


def analyze_symbol(
    symbol: str,
    data: pd.DataFrame,
    equity: float = 10000.0,
    risk_per_trade_pct: float = 1.0,
    timeframe: str = "1d",
) -> Dict:
    if data is None or data.empty:
        return {
            "symbol": symbol,
            "action": "HOLD",
            "reason": "no_data",
        }

    close = data["Close"].dropna().copy()
    if len(close) < 50:
        return {
            "symbol": symbol,
            "action": "HOLD",
            "reason": "insufficient_data",
        }

    votes: Dict[str, str] = {
        "RSI": _strategy_rsi(close),
        "MACD": _strategy_macd(close),
        "SMA_CROSS": _strategy_sma_crossover(close),
        "BOLLINGER": _strategy_bollinger(close),
        "MOMENTUM": _strategy_momentum(close),
    }

    buy_votes = sum(1 for v in votes.values() if v == "BUY")
    sell_votes = sum(1 for v in votes.values() if v == "SELL")
    total_votes = len(votes)

    action = "HOLD"
    if buy_votes > sell_votes:
        action = "BUY"
    elif sell_votes > buy_votes:
        action = "SELL"

    confidence = int(round((max(buy_votes, sell_votes) / total_votes) * 100)) if action != "HOLD" else int(round((1 - abs(buy_votes - sell_votes) / total_votes) * 100))

    entry_price = float(close.iloc[-1])
    # Base risk parameters (can be tuned by strategy context)
    base_stop_pct = 0.02  # 2%
    take_profit_pct = 0.04  # 4% (2R)

    if action == "SELL":
        stop_loss_price = entry_price * (1 + base_stop_pct)
        take_profit_price = entry_price * (1 - take_profit_pct)
    elif action == "BUY":
        stop_loss_price = entry_price * (1 - base_stop_pct)
        take_profit_price = entry_price * (1 + take_profit_pct)
    else:
        stop_loss_price = None
        take_profit_price = None

    risk_capital = equity * (risk_per_trade_pct / 100.0)
    risk_per_unit = entry_price * base_stop_pct if action in ("BUY", "SELL") else entry_price * 0.01
    quantity = int(max(1, math.floor(risk_capital / max(1e-8, risk_per_unit)))) if action in ("BUY", "SELL") else 0
    position_value = quantity * entry_price
    position_percent = (position_value / equity * 100.0) if equity > 0 else 0.0

    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "symbol": symbol,
        "action": action,
        "strategy_votes": votes,
        "confidence": confidence,
        "timeframe": timeframe,
        "entry_price": round(entry_price, 6),
        "stop_loss_pct": round(base_stop_pct * 100, 2) if action in ("BUY", "SELL") else None,
        "take_profit_pct": round(take_profit_pct * 100, 2) if action in ("BUY", "SELL") else None,
        "stop_loss_price": round(stop_loss_price, 6) if stop_loss_price else None,
        "take_profit_price": round(take_profit_price, 6) if take_profit_price else None,
        "quantity": quantity,
        "position_percent": round(position_percent, 2),
        "equity": equity,
        "risk_per_trade_pct": risk_per_trade_pct,
        "timestamp": now_iso,
        "engine": "multi-strategy-v1",
        "order_type": "MARKET",
    }


def merge_signals(signals: List[Dict]) -> List[Dict]:
    # Placeholder for later aggregation across multiple timeframes
    return signals

