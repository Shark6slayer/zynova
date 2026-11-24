from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.client import connect_to_database, close_database_connection, get_database
from app.api.router import api_router
import logging
import re

# Redact sensitive parameters from all logs (tokens, codes, secrets)
SECRET_PATTERNS = [
    re.compile(r"(client_secret=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(code=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(access_token=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(fb_exchange_token=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(refresh_token=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(state=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(smtp_password=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(password=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(catalyst_client_secret=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(catalyst_refresh_token=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(Zoho-oauthtoken\s+)[^&\s]+", re.IGNORECASE),
]

class SensitiveDataRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pat in SECRET_PATTERNS:
                record.msg = pat.sub(r"\1[REDACTED]", record.msg)
        if record.args:
            if isinstance(record.args, dict):
                redacted_args = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        for pat in SECRET_PATTERNS:
                            v = pat.sub(r"\1[REDACTED]", v)
                    redacted_args[k] = v
                record.args = redacted_args
            elif isinstance(record.args, tuple):
                redacted_list = []
                for v in record.args:
                    if isinstance(v, str):
                        for pat in SECRET_PATTERNS:
                            v = pat.sub(r"\1[REDACTED]", v)
                    redacted_list.append(v)
                record.args = tuple(redacted_list)
        return True

# Configure root logger with redaction filter
redaction_filter = SensitiveDataRedactionFilter()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
for handler in logging.root.handlers:
    handler.addFilter(redaction_filter)

# Apply redaction filter to uvicorn loggers specifically (including uvicorn.access)
for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    u_log = logging.getLogger(uvicorn_logger_name)
    u_log.addFilter(redaction_filter)
    for h in u_log.handlers:
        h.addFilter(redaction_filter)

# Suppress httpx and httpcore verbose request URL logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("super_ai_app")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import asyncio
from typing import Optional

from app.core.rate_limit import close_redis_connection

deletion_worker_task: Optional[asyncio.Task] = None

async def _background_deletion_sweeper():
    """Periodic background sweeper that processes expired accounts for cascading deletion."""
    from app.workers.account_deletion_worker import run_deletion_sweep
    while True:
        try:
            await asyncio.sleep(settings.ACCOUNT_DELETION_WORKER_INTERVAL_SECONDS)
            count = await run_deletion_sweep()
            if count > 0:
                logger.info(f"[InAppSweeper] Cascading deletion processed {count} accounts.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[InAppSweeper] Error during deletion sweep: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global deletion_worker_task
    # Startup: connect database and check critical configuration
    logger.info("Initializing SUPER_AI backend services...")
    if settings.JWT_SECRET_KEY == "super_ai_indic_sovereign_dev_secret_key_change_in_production_2026":
        if settings.ENVIRONMENT.lower() == "production":
            raise RuntimeError("CRITICAL SECURITY VIOLATION: Production deployment requires a non-default JWT_SECRET_KEY.")
        else:
            logger.warning("SECURITY WARNING: Using default development JWT_SECRET_KEY. Ensure a custom secret is set in production.")

    await connect_to_database()
    db = get_database()
    if db is not None:
        try:
            await db.revoked_tokens.create_index("expires_at", expireAfterSeconds=0)
            await db.revoked_tokens.create_index("jti", unique=True)
            # Phase 10: Audit ledger sequence uniqueness
            await db.audit_ledger.create_index("sequence", unique=True)
            await db.audit_ledger.create_index("current_hash", unique=True)
            await db.ledger_checkpoints.create_index("end_sequence", unique=True)
            # Phase 12: Registered devices and challenges indexes
            await db.registered_devices.create_index([("user_id", 1), ("public_key_hex", 1)])
            await db.security_challenges.create_index("expires_at", expireAfterSeconds=0)
            # Deletion jobs indexes
            await db.deletion_jobs.create_index([("status", 1), ("permanent_deletion_at", 1)])
            await db.deletion_jobs.create_index("user_id", unique=True)
        except Exception as e:
            logger.warning(f"Index creation on collections skipped: {e}")

    # Start in-app deletion sweeper if enabled
    if settings.ACCOUNT_DELETION_WORKER_ENABLED:
        deletion_worker_task = asyncio.create_task(_background_deletion_sweeper())

    yield
    # Shutdown: clean connections
    logger.info("Shutting down SUPER_AI backend services...")
    if deletion_worker_task is not None:
        deletion_worker_task.cancel()
        try:
            await deletion_worker_task
        except asyncio.CancelledError:
            pass
    await close_redis_connection()
    await close_database_connection()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SUPER_AI Sovereign Indic Super App Backend API",
    lifespan=lifespan
)

# HTTP Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-XSS-Protection"] = "0"
    return response

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include main router
app.include_router(api_router)

# Root-level Legal & Compliance shortcuts
from app.api.routes.legal import get_privacy_policy, get_terms_of_service, get_delete_account_portal

@app.get("/privacy", response_class=Response)
async def root_privacy():
    return await get_privacy_policy()

@app.get("/terms", response_class=Response)
async def root_terms():
    return await get_terms_of_service()

@app.get("/delete-account", response_class=Response)
async def root_delete_account():
    return await get_delete_account_portal()

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "status": "operational",
        "api_docs": "/docs",
        "api_prefix": "/api/v1"
    }
