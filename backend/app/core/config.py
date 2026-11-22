from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
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

    JWT_SECRET_KEY: str
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

    # Production AI Core Engine (Phase 23 & Phase 23.1 Hardening)
    AI_MOCK_MODE: bool = False  # Production safety: mock provider disabled by default
    AI_DEFAULT_PROVIDER: str = "gemini"  # gemini, openai, anthropic, mock
    AI_DEFAULT_MODEL: str = "gemini-2.5-flash"
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

    # Transactional Email & Email Providers Configuration
    EMAIL_PROVIDER: str = "catalyst"  # "catalyst" (primary production), "smtp" (fallback), "mock" (test only)
    
    # Zoho Catalyst Cloud Scale Mail Configuration
    CATALYST_PROJECT_ID: str = "83999000000013024"
    CATALYST_CLIENT_ID: Optional[str] = None
    CATALYST_CLIENT_SECRET: Optional[str] = None
    CATALYST_REFRESH_TOKEN: Optional[str] = None
    CATALYST_ACCOUNTS_URL: str = "https://accounts.zoho.in"
    CATALYST_API_DOMAIN: str = "https://api.catalyst.zoho.in"
    CATALYST_FROM_EMAIL: str = "no-reply@intellidev.in"
    CATALYST_FROM_NAME: str = "ZENOVA"
    CATALYST_ENVIRONMENT: str = "Development"  # "Development" or "Production"
    CATALYST_REQUEST_TIMEOUT_SECONDS: float = 15.0

    # Environment Variable Aliases for Zoho Catalyst (Render & Legacy compatibility)
    ZOHO_CLIENT_ID: Optional[str] = None
    ZOHO_CLIENT_SECRET: Optional[str] = None
    ZOHO_REFRESH_TOKEN: Optional[str] = None
    ZOHO_ACCOUNTS_URL: Optional[str] = None
    CATALYST_API_BASE_URL: Optional[str] = None
    CATALYST_DISPLAY_NAME: Optional[str] = None

    @field_validator("CATALYST_ENVIRONMENT", mode="after")
    @classmethod
    def validate_catalyst_environment(cls, v: str) -> str:
        """Validates that Catalyst environment is either Development or Production."""
        clean = (v or "").strip().capitalize()
        if clean not in ("Development", "Production"):
            logger.warning(f"Invalid CATALYST_ENVIRONMENT '{v}'. Defaulting to 'Development'.")
            return "Development"
        return clean

    @property
    def effective_catalyst_client_id(self) -> Optional[str]:
        return self.CATALYST_CLIENT_ID or self.ZOHO_CLIENT_ID

    @property
    def effective_catalyst_client_secret(self) -> Optional[str]:
        return self.CATALYST_CLIENT_SECRET or self.ZOHO_CLIENT_SECRET

    @property
    def effective_catalyst_refresh_token(self) -> Optional[str]:
        return self.CATALYST_REFRESH_TOKEN or self.ZOHO_REFRESH_TOKEN

    @property
    def effective_catalyst_accounts_url(self) -> str:
        return self.ZOHO_ACCOUNTS_URL or self.CATALYST_ACCOUNTS_URL

    @property
    def effective_catalyst_api_domain(self) -> str:
        return self.CATALYST_API_BASE_URL or self.CATALYST_API_DOMAIN

    @property
    def effective_catalyst_display_name(self) -> str:
        return self.CATALYST_DISPLAY_NAME or self.CATALYST_FROM_NAME
    
    # Required dedicated OTP Hash Secret (used for cryptographic HMAC OTP verification)
    OTP_HASH_SECRET: Optional[str] = None

    # GoDaddy Titan SMTP Configuration (Fallback)
    SMTP_HOST: str = "smtpout.secureserver.net"
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = "no-reply@intellidev.in"
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_SSL: bool = True
    SMTP_FROM_EMAIL: str = "no-reply@intellidev.in"
    SMTP_FROM_NAME: str = "ZENOVA"
    SMTP_TIMEOUT_SECONDS: float = 10.0
    SMTP_MAX_RETRIES: int = 3
    SMTP_RETRY_DELAY_SECONDS: float = 1.0

    # 30-Day Account Deletion & Recovery Lifecycle
    ACCOUNT_DELETION_GRACE_PERIOD_DAYS: int = 30
    ACCOUNT_DELETION_WORKER_ENABLED: bool = True
    ACCOUNT_DELETION_WORKER_INTERVAL_SECONDS: int = 3600  # Check hourly
    ACCOUNT_DELETION_BATCH_SIZE: int = 50

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

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """
        Production startup validation:
        Refuses startup if ENVIRONMENT=production and:
        a) JWT_SECRET_KEY or OTP_HASH_SECRET is missing or empty
        b) either is shorter than 32 characters
        c) JWT_SECRET_KEY equals old default string
           'super_ai_indic_sovereign_dev_secret_key_change_in_production_2026'
        d) both have the same value
        """
        if getattr(self, "ENVIRONMENT", "").lower() == "production":
            jwt_key = getattr(self, "JWT_SECRET_KEY", None)
            otp_secret = getattr(self, "OTP_HASH_SECRET", None)

            # a) Missing or empty
            if not jwt_key or not str(jwt_key).strip():
                raise ValueError("In production, JWT_SECRET_KEY is required and cannot be empty.")
            if not otp_secret or not str(otp_secret).strip():
                raise ValueError("In production, OTP_HASH_SECRET is required and cannot be empty.")

            jwt_str = str(jwt_key).strip()
            otp_str = str(otp_secret).strip()

            # b) Shorter than 32 characters
            if len(jwt_str) < 32:
                raise ValueError(f"In production, JWT_SECRET_KEY must be at least 32 characters (got {len(jwt_str)}).")
            if len(otp_str) < 32:
                raise ValueError(f"In production, OTP_HASH_SECRET must be at least 32 characters (got {len(otp_str)}).")

            # c) Equals old default string
            old_default = "super_ai_indic_sovereign_dev_secret_key_change_in_production_2026"
            if jwt_str == old_default:
                raise ValueError("In production, JWT_SECRET_KEY cannot use the legacy development default key.")

            # d) Both have the same value
            if jwt_str == otp_str:
                raise ValueError("In production, JWT_SECRET_KEY and OTP_HASH_SECRET cannot have the same value.")

        return self

settings = Settings()
