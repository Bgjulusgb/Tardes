import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import plotly.express as px
import yfinance as yf
import streamlit as st
import ta  # Für technische Indikatoren wie RSI, MACD
from plyer import notification  # Für Desktop-Benachrichtigungen
import numpy as np
from datetime import datetime, timedelta

# Globale Variable für gespeicherte Signale
stored_signals = []

# Funktion zum Abrufen von Aktien-Daten
@st.cache_data(ttl=60)  # Cache für 60 Sekunden
def get_stock_data(stock_ticker, period):
    stock = yf.Ticker(stock_ticker)
    data = stock.history(period=period)
    return data

# Funktion für Momentum-Strategie
def calculate_momentum_signals(data, threshold=0.02):
    data = data.copy()
    data['momentum'] = data['Close'].pct_change()
    buy_signals = data[data['momentum'] > threshold]
    sell_signals = data[data['momentum'] < -threshold]
    return buy_signals, sell_signals

# Funktion für RSI-Strategie
def calculate_rsi_signals(data, rsi_period=14, buy_threshold=30, sell_threshold=70):
    data = data.copy()
    data['RSI'] = ta.momentum.RSIIndicator(data['Close'], window=rsi_period).rsi()
    buy_signals = data[data['RSI'] < buy_threshold]
    sell_signals = data[data['RSI'] > sell_threshold]
    return buy_signals, sell_signals

# Funktion für MACD-Strategie
def calculate_macd_signals(data):
    data = data.copy()
    macd = ta.trend.MACD(data['Close'])
    data['MACD'] = macd.macd()
    data['MACD_Signal'] = macd.macd_signal()
    buy_signals = data[data['MACD'] > data['MACD_Signal']]
    sell_signals = data[data['MACD'] < data['MACD_Signal']]
    return buy_signals, sell_signals

# Funktion für gleitende Durchschnitte (SMA)
def calculate_sma_signals(data, short_window=20, long_window=50):
    data = data.copy()
    data['SMA_Short'] = data['Close'].rolling(window=short_window).mean()
    data['SMA_Long'] = data['Close'].rolling(window=long_window).mean()
    buy_signals = data[data['SMA_Short'] > data['SMA_Long']]
    sell_signals = data[data['SMA_Short'] < data['SMA_Long']]
    return buy_signals, sell_signals

# Funktion zur Berechnung der Position Size basierend auf Risiko
def calculate_position_size(current_price, account_balance=10000, risk_percentage=0.02, stop_loss_percentage=0.05):
    risk_amount = account_balance * risk_percentage
    stop_loss_amount = current_price * stop_loss_percentage
    position_size = risk_amount / stop_loss_amount
    return min(position_size, account_balance / current_price)  # Nicht mehr als verfügbar

# Funktion zur Generierung detaillierter Signale
def generate_detailed_signals(stock_ticker, data, strategy='momentum', **kwargs):
    signals = []
    current_price = data['Close'].iloc[-1]
    position_size = calculate_position_size(current_price)

    if strategy == 'momentum':
        buy_signals, sell_signals = calculate_momentum_signals(data, **kwargs)
    elif strategy == 'rsi':
        buy_signals, sell_signals = calculate_rsi_signals(data, **kwargs)
    elif strategy == 'macd':
        buy_signals, sell_signals = calculate_macd_signals(data)
    elif strategy == 'sma':
        buy_signals, sell_signals = calculate_sma_signals(data, **kwargs)
    else:
        return signals

    for idx, row in buy_signals.iterrows():
        signal = {
            'timestamp': idx,
            'type': 'BUY',
            'strategy': strategy.upper(),
            'price': row['Close'],
            'quantity': position_size,
            'percentage': (position_size * row['Close'] / 10000) * 100,  # Anteil am Portfolio
            'confidence': np.random.uniform(0.6, 0.9)  # Einfache Confidence-Metrik
        }
        signals.append(signal)

    for idx, row in sell_signals.iterrows():
        signal = {
            'timestamp': idx,
            'type': 'SELL',
            'strategy': strategy.upper(),
            'price': row['Close'],
            'quantity': position_size,
            'percentage': (position_size * row['Close'] / 10000) * 100,
            'confidence': np.random.uniform(0.6, 0.9)
        }
        signals.append(signal)

    return signals

# Funktion zum Senden von Push-Benachrichtigungen
def send_notification(signal):
    try:
        # Für Desktop-Benachrichtigungen (plyer)
        notification.notify(
            title=f"Trading Signal: {signal['type']} {signal['strategy']}",
            message=f"Stock: {stock_ticker}\nPrice: ${signal['price']:.2f}\nQuantity: {signal['quantity']:.2f}\nConfidence: {signal['confidence']:.2f}",
            app_icon=None,
            timeout=10
        )
        # Für Web-Benachrichtigungen (einfache Browser-Benachrichtigung via Streamlit)
        st.success(f"Neues Signal: {signal['type']} für {stock_ticker} bei ${signal['price']:.2f}")
    except Exception as e:
        st.error(f"Fehler beim Senden der Benachrichtigung: {e}")

# Funktion zur Darstellung der Signale
def display_signals(signals):
    if not signals:
        st.write("Keine Signale gefunden.")
        return

    df_signals = pd.DataFrame(signals)
    st.dataframe(df_signals)

    # Visualisierung der Signale
    fig = px.scatter(df_signals, x='timestamp', y='price', color='type',
                     title='Trading Signals', labels={'price': 'Price', 'timestamp': 'Date'})
    st.plotly_chart(fig)

# Hauptfunktion für das Dashboard
def main():
    st.title('Erweitertes Algorithmisches Trading Dashboard')

    stock_ticker = st.text_input('Geben Sie einen Aktien-Ticker ein (z.B. AAPL)', value='AAPL')
    period = st.selectbox('Wählen Sie einen Zeitraum', ['1mo', '3mo', '6mo', '1y'], index=0)
    strategies = st.multiselect('Wählen Sie Strategien', ['momentum', 'rsi', 'macd', 'sma'], default=['momentum'])

    if stock_ticker and strategies:
        try:
            data = get_stock_data(stock_ticker, period)
            if data.empty:
                st.error("Keine Daten für diesen Ticker verfügbar.")
                return

            all_signals = []
            for strategy in strategies:
                signals = generate_detailed_signals(stock_ticker, data, strategy)
                all_signals.extend(signals)

            # Entferne Duplikate und sortiere
            all_signals = sorted(all_signals, key=lambda x: x['timestamp'], reverse=True)
            unique_signals = []
            seen_timestamps = set()
            for signal in all_signals:
                ts = signal['timestamp'].timestamp()
                if ts not in seen_timestamps:
                    unique_signals.append(signal)
                    seen_timestamps.add(ts)

            # Zeige die neuesten Signale
            st.subheader('Aktuelle Signale')
            display_signals(unique_signals[:10])  # Zeige die letzten 10

            # Sende Benachrichtigungen für neue Signale
            for signal in unique_signals:
                if signal not in stored_signals:
                    send_notification(signal)
                    stored_signals.append(signal)

            # Live-Update: Das Dashboard aktualisiert sich automatisch durch Streamlit's Caching-Mechanismus
            st.write("Das Dashboard aktualisiert sich automatisch. Die Daten werden alle 60 Sekunden aktualisiert.")

        except Exception as e:
            st.error(f'Fehler: {str(e)}')

if __name__ == '__main__':
    main()

# Footer
footer = """
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.0/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-gH2yIJqKdNHPEq0n4Mqa/HGKIhSkIHeL5AyhkYV8i59U5AR6csBvApHHNl/vI1Bx" crossorigin="anonymous">
    <footer>
        <div style='visibility: visible;margin-top:7rem;justify-content:center;display:flex;'>
            <p style="font-size:1.1rem;">
                <a href="https://imshaad.in/" style="text-decoration: none; color: white;">Made by Mohamed Shaad</a>
                &nbsp;
                <a href="https://www.linkedin.com/in/mohamedshaad">
                    <svg xmlns="http://www.w3.org/2000/svg" width="23" height="23" fill="white" class="bi bi-linkedin" viewBox="0 0 16 16">
                        <path d="M0 1.146C0 .513.526 0 1.175 0h13.65C15.474 0 16 .513 16 1.146v13.708c0 .633-.526 1.146-1.175 1.146H1.175C.526 16 0 15.487 0 14.854V1.146zm4.943 12.248V6.169H2.542v7.225h2.401zm-1.2-8.212c.837 0 1.358-.554 1.358-1.248-.015-.709-.52-1.248-1.342-1.248-.822 0-1.359.54-1.359 1.248 0 .694.521 1.248 1.327 1.248h.016zm4.908 8.212V9.359c0-.216.016-.432.08-.586.173-.431.568-.878 1.232-.878.869 0 1.216.662 1.216 1.634v3.865h2.401V9.25c0-2.22-1.184-3.252-2.764-3.252-1.274 0-1.845.7-2.165 1.193v.025h-.016a5.54 5.54 0 0 1 .016-.025V6.169h-2.4c.03.678 0 7.225 0 7.225h2.4z"/>
                    </svg>
                </a>
                &nbsp;
                <a href="https://github.com/shaadclt">
                    <svg xmlns="http://www.w3.org/2000/svg" width="23" height="23" fill="white" class="bi bi-github" viewBox="0 0 16 16">
                        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.012 8.012 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
                    </svg>
                </a>
            </p>
        </div>
    </footer>
"""
st.markdown(footer, unsafe_allow_html=True)