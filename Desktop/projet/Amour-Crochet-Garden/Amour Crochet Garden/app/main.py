"""Amour Crochet Garden - FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import admin, api, public
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logger import logger
from app.core.security_middleware import SecurityHeadersMiddleware
from app.services.tracking import record_page_view, record_referral_visit

_PUBLIC_PATHS = {"/", "/products", "/events", "/cart"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Amour Crochet Garden")
    await init_db()
    yield
    logger.info("Shutting down Amour Crochet Garden")


settings = get_settings()
_docs = "/docs" if settings.debug else None
_redoc = "/redoc" if settings.debug else None
_openapi = "/openapi.json" if settings.debug else None

app = FastAPI(
    title="Amour Crochet Garden",
    lifespan=lifespan,
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=_openapi,
)
# NIS2: security headers first (outermost)
app.add_middleware(SecurityHeadersMiddleware)

# Trusted hosts in production (prevent Host header attacks)
_hosts = settings.allowed_hosts_list
if _hosts and not settings.debug:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

# Secure session: HttpOnly, SameSite=Lax; Secure when https_only=True
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=settings.https_only,
    same_site="lax",
    max_age=24 * 60 * 60,  # 24h session
)

BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/css", StaticFiles(directory=str(BASE_DIR / "static" / "css")), name="css")

app.include_router(public.router, tags=["public"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(api.router, prefix="/api", tags=["api"])


@app.middleware("http")
async def log_requests(request, call_next):
    method = request.method
    path = request.url.path
    qs = str(request.query_params) if request.query_params else ""
    req_msg = f"{method} {path}"
    if method == "GET" and qs:
        req_msg += f" ? {qs}"
    if method in ("POST", "PUT", "PATCH"):
        req_msg += " [body present]"
    logger.info(">>> %s", req_msg)

    try:
        response = await call_next(request)
        logger.info("<<< %s %s -> %d", method, path, response.status_code)

        if request.method == "GET" and response.status_code == 200:
            path_normalized = request.url.path.rstrip("/") or "/"
            if path_normalized in _PUBLIC_PATHS:
                # RGPD: analytics only with visitor consent
                if request.cookies.get("acg_analytics") == "1":
                    ref = request.query_params.get("ref")
                    await record_page_view(request, path_normalized, ref)
                    if ref:
                        await record_referral_visit(request, ref)

        return response
    except Exception as e:
        logger.exception("ERROR: %s %s -> %s", request.method, request.url.path, e)
        raise
