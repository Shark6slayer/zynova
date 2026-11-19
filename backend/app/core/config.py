from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional
import logging
from urllib.parse import urlparse

logger = logging.getLogger("super_ai.config")

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
    ALLOW_DEMO_SEEDING: bool = False

    MONGODB_URI: str = "mongodb://127.0.0.1:27017"
    MONGODB_DB_NAME: str = "super_ai_db"

    JWT_SECRET_KEY: str = "super_ai_indic_sovereign_dev_secret_key_change_in_production_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    CORS_ORIGINS: List[str] = [
        "https://www.intellidev.in",
        "https://intellidev.in",
        "https://zenova.intellidev.in",
        "https://zynova.intellidev.in",
        "https://api.zenova.intellidev.in",
        "https://zynovaapp.vercel.app",
        "https://zynovaapp-git-deployment-atlas-vercel-karuppusamy2.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://localhost",
        "http://localhost",
        "capacitor://localhost",
        "capacitor://"
    ]

    CORS_ORIGIN_REGEX: Optional[str] = r"^https://zynova[a-z0-9-]*-karuppusamy2\.vercel\.app$"

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

    # Production AI Core Engine (Phase 23 & Phase 23.1 Hardening & Phase 8.2 Sovereign Engine)
    SOVEREIGN_AI_MODE: bool = True  # Enforces local proprietary ZenoLM inference
    GPU_FIRST_ENFORCED: bool = True  # Permanent GPU-first execution policy: CUDA mandatory
    AI_ALLOW_CPU_FALLBACK: bool = False  # Refuses silent fallback to CPU unless explicitly configured
    AI_MOCK_MODE: bool = False  # Production safety: mock provider disabled by default
    AI_DEFAULT_PROVIDER: str = "zenolm"  # zenolm (sovereign), gemini, openai, anthropic, mock
    AI_DEFAULT_MODEL: str = "zenolm-micro-2m"
    ZENOLM_CHECKPOINT_PATH: str = "C:/zenoai/checkpoints/zeno_lm_p8_2_torch_best.pt"
    ZENOLM_VOCAB_PATH: str = "C:/zenoai/checkpoints/zeno_tokenizer_vocab.json"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MAX_INPUT_TOKENS: int = 4096
    AI_MAX_OUTPUT_TOKENS: int = 2048
    AI_MAX_TURNS_PER_HOUR: int = 60
    AI_INFERENCE_TIMEOUT_SECONDS: float = 45.0
    AI_ENABLE_AUDIT_LOGGING: bool = True

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

    # Phase 24.1: Unified Media Storage (S3-compatible / Cloudflare R2)
    MEDIA_S3_ACCESS_KEY_ID: Optional[str] = None
    MEDIA_S3_SECRET_ACCESS_KEY: Optional[str] = None
    MEDIA_S3_BUCKET: Optional[str] = None
    MEDIA_S3_REGION: str = "auto"               # "auto" for Cloudflare R2
    MEDIA_S3_ENDPOINT_URL: Optional[str] = None  # e.g. https://<account>.r2.cloudflarestorage.com
    MEDIA_CDN_BASE_URL: Optional[str] = None     # e.g. https://cdn.intellidev.in/public

    # Universal Search & External Ecosystem Integration (Brave Search API)
    BRAVE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_CX: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None

    # Meta / Instagram Graph API Integration (Instagram via Facebook Login)
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_LOGIN_CONFIG_ID: Optional[str] = None
    META_GRAPH_VERSION: str = "v21.0"
    INSTAGRAM_REDIRECT_URI: str = "https://api.zenova.intellidev.in/api/v1/instagram/callback"
    INSTAGRAM_WEBHOOK_VERIFY_TOKEN: Optional[str] = None
    WEB_APP_URL: str = "https://www.intellidev.in"
    MOBILE_DEEP_LINK_SCHEME: str = "zenova"

    @field_validator("INSTAGRAM_REDIRECT_URI", mode="after")
    @classmethod
    def validate_instagram_redirect_uri(cls, v: str) -> str:
        """
        Validates that INSTAGRAM_REDIRECT_URI is a plain HTTPS callback URL:
        - Must start with https://
        - Must NOT have query string (?...) or fragment (#...)
        - Path must end with /instagram/callback
        """
        if not v:
            return v
        try:
            parsed = urlparse(v)
            is_valid = (
                parsed.scheme == "https"
                and bool(parsed.netloc)
                and not parsed.query
                and not parsed.fragment
                and parsed.path.rstrip("/").endswith("/instagram/callback")
            )
            if not is_valid:
                logger.warning(
                    "INSTAGRAM_REDIRECT_URI is invalid: must be a plain https URL without query string or fragment, ending with /instagram/callback. Setting will be marked unconfigured."
                )
                return ""
        except Exception:
            logger.warning("Failed to parse INSTAGRAM_REDIRECT_URI. Setting will be marked unconfigured.")
            return ""
        return v

settings = Settings()
