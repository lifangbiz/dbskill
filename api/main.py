import os
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from api.services.logging_config import setup_logging

setup_logging()

from api.admin.auth import AdminLoginRequired
from api.routes import databases as databases_routes
from api.routes import execute as execute_routes
from api.routes import query as query_routes
from api.routes import schema as schema_routes
from api.admin import router as admin_router
from api.services.models import init_admin_db


def _get_session_secret() -> str:
    """优先级：server.yaml session_secret > 环境变量 SESSION_SECRET > 默认值。"""
    base = Path(__file__).resolve().parents[1]
    server_path = base / "server.yaml"
    if server_path.is_file():
        import yaml
        with server_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        val = raw.get("session_secret") if isinstance(raw.get("session_secret"), str) else None
        if val:
            return val
    return os.environ.get("SESSION_SECRET", "dev-secret-change-in-production")


SESSION_SECRET = _get_session_secret()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_admin_db()
    yield


app = FastAPI(title="DBSkill API", version="0.1.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)


@app.exception_handler(AdminLoginRequired)
def _admin_login_redirect(_request: Request, exc: AdminLoginRequired):
    return RedirectResponse(url=exc.url, status_code=303)


@app.get("/")
async def root():
    return RedirectResponse(url="/admin/login", status_code=302)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


app.include_router(databases_routes.router)
app.include_router(schema_routes.router)
app.include_router(query_routes.router)
app.include_router(execute_routes.router)
app.include_router(admin_router)


def get_app() -> FastAPI:
    """提供给外部（如 uvicorn）导入的工厂方法。"""
    return app

