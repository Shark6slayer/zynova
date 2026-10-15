from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.client import connect_to_database, close_database_connection
from app.api.router import api_router
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("super_ai_app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect database
    logger.info("Initializing SUPER_AI backend services...")
    await connect_to_database()
    yield
    # Shutdown: clean connections
    logger.info("Shutting down SUPER_AI backend services...")
    await close_database_connection()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SUPER_AI Sovereign Indic Super App Backend API",
    lifespan=lifespan
)

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
