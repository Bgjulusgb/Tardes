import re
import logging
from alpaca_trade_api import REST
from alpaca_trade_api.common import URL

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Alpaca API Konfiguration
API_KEY = 'PKKGZTEBC6UNSGUFD1Z7'  # Ersetze mit deinem API-Schlüssel
API_SECRET = 'IFdjAyvhX2RlpUgMwkIqAoedUrEsUqdID2u5hbOh'  # Ersetze mit deinem Secret-Schlüssel
BASE_URL = 'https://paper-api.alpaca.markets'

# API-Verbindung
try:
    api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')
    logger.info("Verbindung zur Alpaca API erfolgreich hergestellt.")
except Exception as e:
    logger.error(f"Fehler bei der Alpaca API-Verbindung: {e}")
    exit(1)

def parse_signals(response):
    """Extrahiert Signale aus der KI-Antwort."""
    try:
        signals_block = re.search(r'\[SIGNAL\](.*?)\[/SIGNAL\]', response, re.DOTALL)
        if not signals_block:
            logger.error("Kein [SIGNAL]-Block gefunden.")
            return []

        signals = signals_block.group(1).strip().split('\n')
        parsed_signals = []

        for signal in signals:
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

def submit_order(signal):
    """Sendet ein Signal an die Alpaca API."""
    try:
        crypto = signal['crypto']
        action = signal['action']
        symbol = f"{crypto}USD"
        qty = 1  # Anpassbar

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
            stop_price = float(signal.get('preis', api.get_latest_trade(symbol).price)) * (1 + float(signal['stop_loss']) / 100)
            api.submit_order(symbol=symbol, qty=qty, side='sell', type='stop', stop_price=stop_price, time_in_force='gtc')
            logger.info(f"Stop-Loss für {symbol} bei {stop_price} gesetzt.")

    except Exception as e:
        logger.error(f"Fehler beim Senden des Auftrags für {signal['crypto']}: {e}")

def main():
    # Beispielantwort der KI
    response = """
    Bericht...
    [SIGNAL]
    BTC: LIMIT_KAUF, Preis=44.500, Take_Profit=+10%, Trailing_Stop=5%, Konfidenz=92%
    ETH: HALTEN, Konfidenz=90%
    XRP: TAKE_PROFIT, Preis=0.98, Konfidenz=91%
    [/SIGNAL]
    """

    signals = parse_signals(response)
    if not signals:
        logger.warning("Keine gültigen Signale gefunden.")
        return

    for signal in signals:
        submit_order(signal)

if __name__ == "__main__":
    main()
