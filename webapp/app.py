from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware

from webapp.routers.api import router as api_router
import os, logging, asyncio

logger = logging.getLogger(__name__)

app = FastAPI(title="Perevozka24 API")


@app.on_event("startup")
async def ensure_db():
    try:
        import psycopg2
        from config import settings
        db_url = settings.DATABASE_URL_SYNC
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("DO $$ BEGIN ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'in_transit'; EXCEPTION WHEN undefined_object THEN NULL; WHEN duplicate_object THEN NULL; END $$")
        for col, typ in [("driver_lat", "DOUBLE PRECISION"), ("driver_lng", "DOUBLE PRECISION"), ("driver_location_updated_at", "TIMESTAMP")]:
            cur.execute(f"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col} {typ}")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS route_subscriptions (
                id SERIAL PRIMARY KEY,
                route VARCHAR(64) NOT NULL,
                username VARCHAR(128) NOT NULL,
                created_at TIMESTAMP DEFAULT now()
            )
        """)
        cur.close()
        conn.close()
        logger.info("Ensured DB schema")
    except Exception as e:
        logger.warning("Could not ensure DB schema: %s", e)


@app.on_event("startup")
async def start_self_ping():
    async def keep_alive():
        from config import settings
        import httpx
        url = settings.PUBLIC_URL.rstrip("/") + "/health"
        while True:
            await asyncio.sleep(180)
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    logger.info("Self-ping %s -> %s", url, resp.status_code)
            except Exception as e:
                logger.warning("Self-ping failed: %s", e)
    asyncio.create_task(keep_alive())


@app.on_event("startup")
async def start_stale_order_cleanup():
    from datetime import datetime, timedelta
    from sqlalchemy import update
    from db.engine import async_session
    from db.models import Order, OrderStatus

    _cleanup_tasks = []

    async def cleanup():
        while True:
            try:
                cutoff = datetime.utcnow() - timedelta(hours=24)
                async with async_session() as session:
                    result = await session.execute(
                        update(Order)
                        .where(
                            Order.date_time < cutoff,
                            Order.status.in_([OrderStatus.new, OrderStatus.active]),
                        )
                        .values(status=OrderStatus.cancelled)
                    )
                    await session.commit()
                    if result.rowcount:
                        logger.info("Cancelled %s stale orders", result.rowcount)
            except Exception as e:
                logger.warning("Stale order cleanup failed: %s", e)
            await asyncio.sleep(3600)

    _cleanup_tasks.append(asyncio.create_task(cleanup()))


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(NoCacheMiddleware)
app.include_router(api_router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/app", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
