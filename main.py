import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.engine.engine import get_config, run_analysis
from app.broker.alpaca import submit_order as broker_submit
from app.notify.push import SubscriptionStore, ensure_vapid_keys, send_push_to_all


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


app = FastAPI(title="Trading Signals Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.getcwd(), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


subscriptions = SubscriptionStore(file_path=os.path.join(os.getcwd(), "subscriptions.json"))
vapid = ensure_vapid_keys()


class Broadcaster:
    def __init__(self) -> None:
        self.clients: List[asyncio.Queue] = []

    async def stream(self) -> AsyncGenerator[bytes, None]:
        queue: asyncio.Queue = asyncio.Queue()
        self.clients.append(queue)
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n".encode("utf-8")
        except asyncio.CancelledError:
            pass
        finally:
            try:
                self.clients.remove(queue)
            except ValueError:
                pass

    async def publish(self, data: Dict) -> None:
        stale: List[asyncio.Queue] = []
        for q in list(self.clients):
            try:
                q.put_nowait(data)
            except Exception:
                stale.append(q)
        for q in stale:
            try:
                self.clients.remove(q)
            except ValueError:
                pass


broadcaster = Broadcaster()


@app.get("/")
async def root() -> HTMLResponse:
    try:
        html = open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8").read()
        return HTMLResponse(html)
    except Exception:
        return HTMLResponse("<h1>Trading Signals</h1>")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    path = os.path.join(static_dir, "sw.js")
    return FileResponse(path, media_type="application/javascript")


@app.get("/events")
async def events() -> StreamingResponse:
    async def generator():
        # Initial heartbeat to establish connection
        yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.now(timezone.utc).isoformat()})}\n\n".encode("utf-8")
        async for chunk in broadcaster.stream():
            yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/config")
async def get_server_config() -> JSONResponse:
    cfg = get_config()
    return JSONResponse({
        "symbols": cfg["symbols"],
        "period": cfg["period"],
        "interval": cfg["interval"],
        "auto_trade": cfg["auto_trade"],
    })


@app.get("/vapid")
async def get_vapid() -> JSONResponse:
    pub = vapid.get("public") if vapid else None
    return JSONResponse({"publicKey": pub})


@app.post("/subscribe")
async def subscribe(req: Request) -> JSONResponse:
    body = await req.json()
    subscriptions.add(body)
    return JSONResponse({"ok": True})


@app.post("/analyze")
async def analyze() -> JSONResponse:
    cfg = get_config()
    signals = run_analysis(cfg["symbols"], cfg["equity"], cfg["risk_pct"], cfg["period"], cfg["interval"], cfg["timeframe"])
    await broadcaster.publish({"type": "signals", "data": signals})
    return JSONResponse({"signals": signals})


async def run_cycle() -> None:
    cfg = get_config()
    try:
        signals = run_analysis(cfg["symbols"], cfg["equity"], cfg["risk_pct"], cfg["period"], cfg["interval"], cfg["timeframe"])
        await broadcaster.publish({"type": "signals", "data": signals})
        # Optional: auto trade + push
        notified = 0
        traded = 0
        for sig in signals:
            if cfg["auto_trade"]:
                if broker_submit(sig):
                    traded += 1
            payload = {
                "title": f"Signal {sig['action']} {sig['symbol']}",
                "body": f"Preis {sig['entry_price']} • Menge {sig['quantity']} • {sig['confidence']}%",
                "symbol": sig["symbol"],
                "action": sig["action"],
                "quantity": sig["quantity"],
                "position_percent": sig["position_percent"],
                "entry_price": sig["entry_price"],
                "take_profit_price": sig.get("take_profit_price"),
                "stop_loss_price": sig.get("stop_loss_price"),
            }
            notified += send_push_to_all(subscriptions, payload, vapid)
        logger.info(f"Zyklus: {len(signals)} Signale, {traded} Trades, {notified} Push gesendet")
    except Exception as exc:
        logger.exception(f"Fehler im Zyklus: {exc}")


@app.on_event("startup")
async def on_startup() -> None:
    async def scheduler() -> None:
        await asyncio.sleep(0.1)
        while True:
            await run_cycle()
            await asyncio.sleep(60)
    asyncio.create_task(scheduler())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
