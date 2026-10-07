import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings, reload_settings
from services.aws_service import get_aws_service
from services.hazard_monitor import HazardMonitor
from routes.webhook import router as webhook_router
from routes.admin_api import router as admin_router
from routes.admin_api import dashboard_router

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSE broadcaster — a simple async pub/sub for real-time dashboard updates
# ---------------------------------------------------------------------------
class SSEBroadcaster:
    """Holds a set of active SSE client queues and broadcasts JSON events."""

    def __init__(self):
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._queues.discard(q)

    async def publish(self, event_type: str, data: dict):
        """Fire-and-forget broadcast to all connected clients."""
        payload = json.dumps({"type": event_type, "data": data})
        dead: list[asyncio.Queue] = []
        for q in list(self._queues):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._queues.discard(q)

    @property
    def connection_count(self) -> int:
        return len(self._queues)


# Singleton broadcaster — imported by admin_api.py
sse_broadcaster = SSEBroadcaster()


async def hazard_monitor_loop():
    """Background task: polls for hazards every N seconds in real mode."""
    settings = get_settings()
    await asyncio.sleep(5)
    while True:
        try:
            if not settings.demo_mode:
                logger.info("🔍 Running hazard monitor scan...")
                monitor = HazardMonitor()
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, monitor.run_scan)
                logger.info(f"Hazard scan complete: {result}")
                # Broadcast full refresh to all SSE clients after a live scan
                await sse_broadcaster.publish("refresh", {"reason": "hazard_scan"})
            else:
                logger.debug("Demo mode active — skipping live hazard scan")
        except Exception as e:
            logger.error(f"Error in hazard monitor loop: {e}")
        await asyncio.sleep(settings.hazard_poll_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("🚀 NOVA-S DISASTER MANAGEMENT SYSTEM")
    logger.info("=" * 60)
    settings = reload_settings()  # force-reload .env on every startup
    mode = "DEMO" if settings.demo_mode else "REAL"
    logger.info(f"Mode: {mode}")
    logger.info(f"Monitor Center: ({settings.monitor_lat}, {settings.monitor_lon})")

    aws = get_aws_service()
    mock_status = "MOCK" if aws.use_mock else "AWS LIVE"
    logger.info(f"AWS Backend: {mock_status}")

    monitor_task = asyncio.create_task(hazard_monitor_loop())
    logger.info("✅ Background hazard monitor started")
    logger.info(f"📊 Dashboard: http://localhost:8000/dashboard")
    logger.info(f"📡 SSE stream: http://localhost:8000/api/admin/events")
    logger.info("=" * 60)

    yield

    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    logger.info("🛑 Disaster Management System shut down")


app = FastAPI(
    title="NOVA-S Disaster Management System",
    description="Integrated multi-hazard detection, WhatsApp emergency response, and AI triage system",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach broadcaster so admin_api can import it
app.state.sse_broadcaster = sse_broadcaster


# ---------------------------------------------------------------------------
# SSE endpoint — one persistent connection per browser tab
# ---------------------------------------------------------------------------
@app.get("/api/admin/events")
async def sse_events(request: Request):
    """Server-Sent Events stream.  Each event is a JSON line prefixed with
    'data: '.  The client reconnects automatically on drop."""
    broadcaster: SSEBroadcaster = request.app.state.sse_broadcaster
    q = broadcaster.subscribe()

    async def event_stream() -> AsyncGenerator[str, None]:
        # Send an immediate heartbeat so the browser knows the connection is alive
        yield "data: {\"type\": \"connected\", \"data\": {}}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping every 20 s to prevent proxy timeouts
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disables nginx buffering
            "Connection": "keep-alive",
        },
    )


# Include routers
app.include_router(webhook_router)
app.include_router(admin_router)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/health")
async def health():
    settings = get_settings()
    aws = get_aws_service()
    return {
        "status": "healthy",
        "system": "NOVA-S Disaster Management System",
        "mode": "demo" if settings.demo_mode else "real",
        "aws_backend": "mock" if aws.use_mock else "live",
        "version": "3.0.0",
        "sse_connections": app.state.sse_broadcaster.connection_count,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
