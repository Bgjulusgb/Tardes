import re
import os
import logging
from typing import List, Dict, Any, Optional
from alpaca_trade_api import REST

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Alpaca API Konfiguration aus Umgebung
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_API_SECRET = os.getenv('ALPACA_API_SECRET')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

def get_alpaca_client() -> REST:
    """Erstellt und gibt einen Alpaca REST-Client zurück."""
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise RuntimeError('ALPACA_API_KEY/ALPACA_API_SECRET sind nicht gesetzt')
    return REST(ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_BASE_URL, api_version='v2')

def parse_signals(response: str) -> List[Dict[str, Any]]:
    """Extrahiert Signale aus der KI-Antwort."""
    try:
        signals_block = re.search(r'\[SIGNAL\](.*?)\[/SIGNAL\]', response, re.DOTALL)
        if not signals_block:
            logger.error("Kein [SIGNAL]-Block gefunden.")
            return []

        signals = signals_block.group(1).strip().split('\n')
        parsed_signals = []

        for signal in signals:
            if not signal.strip():
                continue
            parts = signal.split(': ')
            if len(parts) < 2:
                logger.warning(f"Ungültiges Signalformat: {signal}")
                continue

            crypto = parts[0]
            action_data = parts[1].split(', ')
            action = action_data[0]

            # Extrahiere Parameter
            params = {'crypto': crypto, 'action': action}
            for item in action_data[1:]:
                if '=' in item:
                    key, value = item.split('=')
                    key = key.lower().replace(' ', '_')
                    params[key] = value.replace('%', '')

            parsed_signals.append(params)
        return parsed_signals
    except Exception as e:
        logger.error(f"Fehler beim Parsen der Signale: {e}")
        return []

def submit_order(signal: Dict[str, Any], api: Optional[REST] = None) -> None:
    """Sendet ein Signal an die Alpaca API."""
    try:
        if api is None:
            api = get_alpaca_client()
        crypto = signal['crypto']
        action = signal['action']
        symbol = f"{crypto}USD"
        # Menge aus Signal oder Standard 1
        qty_raw = signal.get('menge') or signal.get('qty') or 1
        qty = float(qty_raw)

        if action == 'KAUF':
            api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
            logger.info(f"Marktkauf für {symbol} ausgeführt.")

        elif action == 'LIMIT_KAUF':
            limit_price = float(signal.get('preis'))
            api.submit_order(symbol=symbol, qty=qty, side='buy', type='limit', limit_price=limit_price, time_in_force='gtc')
            logger.info(f"Limit-Kauf für {symbol} bei {limit_price} platziert.")

        elif action == 'VERKAUF':
            api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
            logger.info(f"Marktverkauf für {symbol} ausgeführt.")

        elif action == 'LIMIT_VERKAUF':
            limit_price = float(signal.get('preis'))
            api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=limit_price, time_in_force='gtc')
            logger.info(f"Limit-Verkauf für {symbol} bei {limit_price} platziert.")

        elif action == 'TAKE_PROFIT':
            take_profit_price = float(signal.get('preis'))
            api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=take_profit_price, time_in_force='gtc')
            logger.info(f"Take-Profit für {symbol} bei {take_profit_price} platziert.")

        elif action == 'TRAILING_STOP':
            trail_percent = float(signal.get('trailing_stop')) / 100
            api.submit_order(symbol=symbol, qty=qty, side='sell', type='trailing_stop', trail_percent=trail_percent, time_in_force='gtc')
            logger.info(f"Trailing Stop für {symbol} mit {trail_percent*100}% gesetzt.")

        elif action == 'HALTEN':
            logger.info(f"{symbol}: Keine Aktion erforderlich.")

        # Zusätzliche Stop-Loss-Order, falls angegeben
        if 'stop_loss' in signal:
            base_price = signal.get('preis')
            latest_price = None
            if base_price is not None:
                try:
                    latest_price = float(base_price)
                except Exception:
                    latest_price = None
            if latest_price is None:
                try:
                    trade = api.get_latest_trade(symbol)
                    latest_price = float(getattr(trade, 'price', 0))
                except Exception:
                    latest_price = None
            if latest_price and latest_price > 0:
                stop_price = latest_price * (1 + float(signal['stop_loss']) / 100)
                api.submit_order(symbol=symbol, qty=qty, side='sell', type='stop', stop_price=stop_price, time_in_force='gtc')
                logger.info(f"Stop-Loss für {symbol} bei {stop_price} gesetzt.")
            else:
                logger.warning(f"Kein gültiger Preis für Stop-Loss bei {symbol} verfügbar.")

    except Exception as e:
        logger.error(f"Fehler beim Senden des Auftrags für {signal.get('crypto', 'UNBEKANNT')}: {e}")

def run_demo_from_text(response: str) -> None:
    """Parst eine Textantwort und sendet resultierende Orders (nur zu Testzwecken)."""
    signals = parse_signals(response)
    if not signals:
        logger.warning("Keine gültigen Signale gefunden.")
        return
    api = get_alpaca_client()
    for signal in signals:
        submit_order(signal, api=api)

__all__ = [
    'get_alpaca_client',
    'parse_signals',
    'submit_order',
    'run_demo_from_text',
]
