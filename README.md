# Signals Engine (FastAPI + SSE)

## Setup

1) Python 3.10+
2) Install dependencies:

```
pip install -r requirements.txt
```

3) Environment variables:

```
export ALPACA_API_KEY=your_key
export ALPACA_API_SECRET=your_secret
export ALPACA_BASE_URL=https://paper-api.alpaca.markets
export SYMBOLS=BTC,ETH
```

## Run

```
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Open dashboard: http://localhost:8000/

The server pushes live signals every minute via SSE to the dashboard and triggers orders via Alpaca. Browser notifications show new signals including price, amount, share, and strategy.