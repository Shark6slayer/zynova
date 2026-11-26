import os
import json
import base64
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger("super_ai.firebase_service")

_firebase_app = None

def get_firebase_app():
    """
    Lazily initialises and returns the firebase_admin default App instance.
    Credentials are read from settings.FIREBASE_SERVICE_ACCOUNT_JSON (raw JSON or base64).
    Never logs credentials.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    import firebase_admin
    from firebase_admin import credentials

    # Check if default app is already initialized in firebase_admin._apps
    try:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app
    except ValueError:
        pass

    raw_cfg = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    if not raw_cfg or not raw_cfg.strip():
        if settings.ENVIRONMENT.lower() == "production":
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is missing or empty in production.")
        # Development fallback / test mode: initialize without credential or mock
        try:
            _firebase_app = firebase_admin.initialize_app()
            return _firebase_app
        except Exception as e:
            logger.warning(f"Firebase app initialized without credentials: {e}")
            return None

    raw_cfg = raw_cfg.strip()
    cred_dict: Optional[Dict[str, Any]] = None

    # Try raw JSON first
    if raw_cfg.startswith("{") and raw_cfg.endswith("}"):
        try:
            cred_dict = json.loads(raw_cfg)
        except Exception as e:
            logger.error("Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON as JSON.")
            raise ValueError("Invalid FIREBASE_SERVICE_ACCOUNT_JSON format") from e
    else:
        # Try base64 decoding
        try:
            decoded_bytes = base64.b64decode(raw_cfg)
            cred_dict = json.loads(decoded_bytes.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to decode FIREBASE_SERVICE_ACCOUNT_JSON as base64 JSON.")
            raise ValueError("Invalid FIREBASE_SERVICE_ACCOUNT_JSON format") from e

    cred = credentials.Certificate(cred_dict)
    _firebase_app = firebase_admin.initialize_app(cred)
    logger.info("Successfully initialized Firebase Admin SDK.")
    return _firebase_app
