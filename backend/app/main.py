from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.client import connect_to_database, close_database_connection, get_database
from app.api.router import api_router
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("super_ai_app")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.rate_limit import close_redis_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
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
        except Exception as e:
            logger.warning(f"Index creation on collections skipped: {e}")

    yield
    # Shutdown: clean connections
    logger.info("Shutting down SUPER_AI backend services...")
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include main router
app.include_router(api_router)

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "status": "operational",
        "api_docs": "/docs",
        "api_prefix": "/api/v1"
    }
