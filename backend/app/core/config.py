from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

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
        "https://zynova.intellidev.in",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://localhost",
        "http://localhost",
        "capacitor://localhost"
    ]

    # Shared Rate Limiting & Redis
    REDIS_URL: Optional[str] = None
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 2.0
    TRUSTED_PROXIES: List[str] = ["127.0.0.1", "::1", "localhost"]
    RATE_LIMIT_FAIL_CLOSED_IN_PROD: bool = True

    # Media Malware Scanner (ClamAV)
    CLAMAV_HOST: Optional[str] = None
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT_SECONDS: float = 5.0
    CLAMAV_REQUIRED_IN_PRODUCTION: bool = True

    # Cryptographic Key Management (Phase 9)
    # 256-bit base64-encoded or hex string master key (or KMS provider URI)
    KMS_PROVIDER: str = "local_env"  # local_env, aws_kms, gcp_kms, hsm
    MASTER_ENCRYPTION_KEY: Optional[str] = "dev_master_key_super_ai_indic_sovereign_32bytes_sec"
    ACTIVE_KEY_VERSION: str = "v1"

    # Private Cryptographic Audit Ledger (Phase 10)
    AUDIT_LEDGER_ENABLED: bool = True
    AUDIT_LEDGER_SIGNER_KEY_HEX: Optional[str] = None  # 32-byte Ed25519 private key seed (hex)
    AUDIT_LEDGER_PSEUDONYM_SALT: str = "super_ai_ledger_pseudonym_salt_indic_sovereign_2026"
    AUDIT_LEDGER_CHECKPOINT_INTERVAL_EVENTS: int = 100

    # Hybrid Public Blockchain Anchoring (Phase 11)
    BLOCKCHAIN_ANCHOR_ENABLED: bool = False
    BLOCKCHAIN_NETWORK: str = "local_simulated"  # local_simulated, polygon_amoy, arbitrum_sepolia
    BLOCKCHAIN_RPC_URL: Optional[str] = None
    BLOCKCHAIN_CHAIN_ID: int = 1337  # 1337 local, 80002 Amoy, 421614 Arb Sepolia
    BLOCKCHAIN_CONTRACT_ADDRESS: Optional[str] = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    BLOCKCHAIN_WALLET_ADDRESS: Optional[str] = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    BLOCKCHAIN_DRY_RUN: bool = True
    BLOCKCHAIN_REQUIRED_CONFIRMATIONS: int = 12
    BLOCKCHAIN_MAX_FEE_GWEI: float = 50.0
    BLOCKCHAIN_RPC_TIMEOUT_SECONDS: float = 10.0

settings = Settings()
