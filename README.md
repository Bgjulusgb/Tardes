# Verbessertes Algorithmisches Trading Dashboard

Dieses Skript ist ein erweitertes Streamlit-Dashboard für algorithmisches Trading, das mehrere Strategien unterstützt und Live-Signale mit Push-Benachrichtigungen bietet.

## Funktionen

- **Mehrere Trading-Strategien**: Momentum, RSI, MACD, Gleitende Durchschnitte (SMA)
- **Detaillierte Signale**: Enthält Menge, Anteil, Entry/Exit-Preise, Confidence
- **Live-Updates**: Automatische Aktualisierung der Daten alle 60 Sekunden
- **Push-Benachrichtigungen**: Desktop- und Web-Benachrichtigungen für neue Signale
- **Interaktives Dashboard**: Wählen Sie Aktien-Ticker, Zeitraum und Strategien

## Installation

1. Installieren Sie die erforderlichen Bibliotheken:
   ```bash
   pip install yfinance ta streamlit plotly plyer
   ```

2. Führen Sie das Dashboard aus:
   ```bash
   streamlit run improved_trading_dashboard.py
   ```

## Verwendung

1. Geben Sie einen Aktien-Ticker ein (z.B. AAPL).
2. Wählen Sie einen Zeitraum (1mo, 3mo, 6mo, 1y).
3. Wählen Sie eine oder mehrere Strategien (Momentum, RSI, MACD, SMA).
4. Das Dashboard zeigt die neuesten Signale an und sendet Benachrichtigungen für neue Signale.

## Anmerkungen

- Die Push-Benachrichtigungen funktionieren als Desktop-Benachrichtigungen (mit plyer) und als Web-Benachrichtigungen in Streamlit.
- Für echte Web-Push-Nachrichten könnte eine Integration mit Services wie Firebase erforderlich sein.
- Die Live-Updates basieren auf Streamlit's Caching-Mechanismus.

## Ursprünglicher Code

Der ursprüngliche Code wurde modularisiert, erweitert und verbessert, um die Anforderungen zu erfüllen.