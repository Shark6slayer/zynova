from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENVIRONMENT: str = "development"
    APP_NAME: str = "SUPER_AI_BACKEND"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    MONGODB_URI: str = "mongodb://127.0.0.1:27017"
    MONGODB_DB_NAME: str = "super_ai_db"

    JWT_SECRET_KEY: str = "super_ai_indic_sovereign_dev_secret_key_change_in_production_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://localhost",
        "http://localhost",
        "capacitor://localhost"
    ]

settings = Settings()
