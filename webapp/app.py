from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware

from webapp.routers.api import router as api_router
import os, logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Perevozka24 API")


@app.on_event("startup")
async def ensure_enum_values():
    try:
        import psycopg2
        from config import settings
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = "postgresql://" + db_url[len("postgresql+asyncpg://"):]
        elif db_url.startswith("postgresql+psycopg://"):
            db_url = "postgresql://" + db_url[len("postgresql+psycopg://"):]
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("DO $$ BEGIN ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'in_transit'; EXCEPTION WHEN undefined_object THEN NULL; WHEN duplicate_object THEN NULL; END $$")
        cur.close()
        conn.close()
        logger.info("Ensured in_transit enum value exists")
    except Exception as e:
        logger.warning("Could not ensure enum values: %s", e)


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
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
