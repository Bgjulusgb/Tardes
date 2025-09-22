import datetime as dt
from typing import List, Dict, Any

import pandas as pd
import yfinance as yf


def _download_ohlc(symbol: str, lookback_days: int = 120, interval: str = '1h') -> pd.DataFrame:
    end = dt.datetime.utcnow()
    start = end - dt.timedelta(days=lookback_days)
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, interval=interval)
    if df.empty:
        return df
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume',
    })
    return df


def momentum_strategy(symbol: str) -> List[Dict[str, Any]]:
    df = _download_ohlc(symbol)
    if df.empty or len(df) < 2:
        return []
    df['ret'] = df['close'].pct_change()
    last_row = df.iloc[-1]
    signal = None
    if last_row['ret'] > 0:
        signal = {
            'crypto': symbol.replace('USD', ''),
            'action': 'KAUF',
            'preis': float(last_row['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': 'Momentum',
            'konfidenz': min(99, round(last_row['ret'] * 10000, 2)),
        }
    elif last_row['ret'] < 0:
        signal = {
            'crypto': symbol.replace('USD', ''),
            'action': 'VERKAUF',
            'preis': float(last_row['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': 'Momentum',
            'konfidenz': min(99, round(abs(last_row['ret']) * 10000, 2)),
        }
    return [signal] if signal else []


def sma_crossover_strategy(symbol: str, fast: int = 10, slow: int = 30) -> List[Dict[str, Any]]:
    df = _download_ohlc(symbol)
    if df.empty or len(df) < slow + 2:
        return []
    df['sma_fast'] = df['close'].rolling(window=fast).mean()
    df['sma_slow'] = df['close'].rolling(window=slow).mean()
    if df[['sma_fast', 'sma_slow']].isna().any().any():
        return []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signal = None
    if prev['sma_fast'] <= prev['sma_slow'] and last['sma_fast'] > last['sma_slow']:
        signal = {
            'crypto': symbol.replace('USD', ''),
            'action': 'KAUF',
            'preis': float(last['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': f'SMA{fast}/{slow}',
            'konfidenz': 80,
        }
    elif prev['sma_fast'] >= prev['sma_slow'] and last['sma_fast'] < last['sma_slow']:
        signal = {
            'crypto': symbol.replace('USD', ''),
            'action': 'VERKAUF',
            'preis': float(last['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': f'SMA{fast}/{slow}',
            'konfidenz': 80,
        }
    return [signal] if signal else []


def rsi_strategy(symbol: str, period: int = 14, oversold: int = 30, overbought: int = 70) -> List[Dict[str, Any]]:
    df = _download_ohlc(symbol)
    if df.empty or len(df) < period + 2:
        return []
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / (avg_loss.replace(0, 1e-9))
    rsi = 100 - (100 / (1 + rs))
    df['rsi'] = rsi
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signal = None
    if prev['rsi'] < oversold and last['rsi'] >= oversold:
        signal = {
            'crypto': symbol.replace('USD', ''),
            'action': 'KAUF',
            'preis': float(last['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': f'RSI{period}',
            'konfidenz': 75,
        }
    elif prev['rsi'] > overbought and last['rsi'] <= overbought:
        signal = {
            'crypto': symbol.replace('USD', ''),
            'action': 'VERKAUF',
            'preis': float(last['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': f'RSI{period}',
            'konfidenz': 75,
        }
    return [signal] if signal else []


def macd_strategy(symbol: str, fast: int = 12, slow: int = 26, signal_len: int = 9) -> List[Dict[str, Any]]:
    df = _download_ohlc(symbol)
    if df.empty or len(df) < slow + signal_len + 2:
        return []
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal_len, adjust=False).mean()
    df['macd'] = macd
    df['signal'] = signal_line
    last = df.iloc[-1]
    prev = df.iloc[-2]
    out = []
    if prev['macd'] <= prev['signal'] and last['macd'] > last['signal']:
        out.append({
            'crypto': symbol.replace('USD', ''),
            'action': 'KAUF',
            'preis': float(last['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': 'MACD',
            'konfidenz': 78,
        })
    elif prev['macd'] >= prev['signal'] and last['macd'] < last['signal']:
        out.append({
            'crypto': symbol.replace('USD', ''),
            'action': 'VERKAUF',
            'preis': float(last['close']),
            'menge': 1,
            'anteil': 100,
            'strategie': 'MACD',
            'konfidenz': 78,
        })
    return out


def generate_signals_for_symbols(symbols: List[str]) -> List[Dict[str, Any]]:
    """Führt mehrere Strategien aus und aggregiert Signale."""
    all_signals: List[Dict[str, Any]] = []
    for sym in symbols:
        # yfinance erwartet z.B. 'BTC-USD'
        yf_symbol = sym if sym.endswith('-USD') else f'{sym}-USD'
        all_signals.extend(momentum_strategy(yf_symbol))
        all_signals.extend(sma_crossover_strategy(yf_symbol))
        all_signals.extend(rsi_strategy(yf_symbol))
        all_signals.extend(macd_strategy(yf_symbol))
    # Dedup oder Merger könnten hier ergänzt werden
    return all_signals


__all__ = [
    'momentum_strategy',
    'sma_crossover_strategy',
    'rsi_strategy',
    'macd_strategy',
    'generate_signals_for_symbols',
]

