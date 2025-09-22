import asyncio
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from sse_starlette.sse import EventSourceResponse

from main import submit_order
from strategies import generate_signals_for_symbols


app = FastAPI(title='Signal Engine')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)


class Broadcaster:
    def __init__(self) -> None:
        self.connections: List[asyncio.Queue] = []

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.connections.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self.connections.remove(q)
        except ValueError:
            pass

    async def publish(self, data: Dict[str, Any]) -> None:
        for q in list(self.connections):
            try:
                await q.put(data)
            except Exception:
                pass


broadcaster = Broadcaster()


SYMBOLS_ENV = os.getenv('SYMBOLS', 'BTC,ETH')
SYMBOLS: List[str] = [s.strip().upper() for s in SYMBOLS_ENV.split(',') if s.strip()]


async def scheduler_loop() -> None:
    # Läuft dauerhaft und prüft jede Minute
    while True:
        try:
            signals = generate_signals_for_symbols(SYMBOLS)
            # Push an Dashboard und Orders auslösen
            for s in signals:
                s['timestamp'] = datetime.now(timezone.utc).isoformat()
                await broadcaster.publish({'type': 'signal', 'payload': s})
                # Optional: direkt Order schicken
                try:
                    submit_order(s)
                except Exception as e:
                    await broadcaster.publish({'type': 'error', 'payload': {'message': str(e)}})
        except Exception as e:
            await broadcaster.publish({'type': 'error', 'payload': {'message': str(e)}})

        await asyncio.sleep(60)


@app.on_event('startup')
async def on_startup() -> None:
    asyncio.create_task(scheduler_loop())


@app.get('/', response_class=HTMLResponse)
async def root() -> HTMLResponse:
    dashboard_path = os.path.join(os.path.dirname(__file__), 'static', 'dashboard.html')
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return HTMLResponse('<h3>Dashboard fehlt</h3>')


@app.get('/events')
async def sse(request: Request) -> EventSourceResponse:
    client = await broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(client.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    yield {'event': 'ping', 'data': json.dumps({'ts': datetime.utcnow().isoformat()})}
                else:
                    yield {'event': 'message', 'data': json.dumps(msg)}
        finally:
            broadcaster.unsubscribe(client)

    return EventSourceResponse(event_generator())

