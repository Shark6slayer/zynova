"""
SUPER_AI — Sovereign Authentication OTP & Password Reset Service
Provides cryptographically secure OTP generation, HMAC-SHA256 hashing,
Upstash Redis storage with in-memory fallback, rate limiting, and single-use enforcement.
"""

import hmac
import hashlib
import secrets
import json
import time
import uuid
import logging
from typing import Optional, Tuple, Dict, Any
from app.core.config import settings
from app.core.rate_limit import get_redis_client

logger = logging.getLogger("super_ai.otp_service")

# In-memory storage fallback if Redis is temporarily unreachable
_memory_store: Dict[str, Dict[str, Any]] = {}

EMAIL_VERIFY_PREFIX = "email_verify:"
EMAIL_VERIFY_CD_PREFIX = "email_verify_cd:"
PWD_RESET_PREFIX = "pwd_reset:"
PWD_RESET_CD_PREFIX = "pwd_reset_cd:"
PWD_RESET_TOKEN_PREFIX = "pwd_reset_token:"

VERIFY_OTP_TTL_SECONDS = 300      # 5 minutes
RESET_CODE_TTL_SECONDS = 600      # 10 minutes
COOLDOWN_TTL_SECONDS = 60         # 60 seconds resend cooldown
MAX_ATTEMPTS = 5


def generate_six_digit_code() -> str:
    """Generates a cryptographically secure 6-digit numeric string."""
    return f"{secrets.randbelow(900000) + 100000:06d}"


def hash_code(code: str) -> str:
    """Hashes a 6-digit code using HMAC-SHA256 with the server's master secret."""
    clean_code = code.strip().encode("utf-8")
    secret = settings.JWT_SECRET_KEY.encode("utf-8")
    return hmac.new(secret, clean_code, hashlib.sha256).hexdigest()


def verify_code_hash(submitted_code: str, stored_hash: str) -> bool:
    """Constant-time verification of submitted code against stored HMAC hash."""
    computed_hash = hash_code(submitted_code)
    return hmac.compare_digest(computed_hash, stored_hash)


async def _set_store(key: str, data: Dict[str, Any], ttl_seconds: int) -> None:
    """Stores data in Redis with TTL, falling back to in-memory store."""
    serialized = json.dumps(data)
    try:
        redis = await get_redis_client()
        if redis:
            await redis.set(key, serialized, ex=ttl_seconds)
            return
    except Exception as e:
        logger.warning(f"Redis write error for key {key}: {e}. Using in-memory fallback.")

    # Fallback to local memory store
    _memory_store[key] = {
        "val": serialized,
        "exp": time.time() + ttl_seconds
    }


async def _get_store(key: str) -> Optional[Dict[str, Any]]:
    """Retrieves data from Redis or in-memory store, evaluating TTL."""
    try:
        redis = await get_redis_client()
        if redis:
            raw = await redis.get(key)
            if raw:
                return json.loads(raw)
            return None
    except Exception as e:
        logger.warning(f"Redis read error for key {key}: {e}. Checking in-memory fallback.")

    item = _memory_store.get(key)
    if not item:
        return None
    if time.time() > item["exp"]:
        del _memory_store[key]
        return None
    return json.loads(item["val"])


async def _delete_store(key: str) -> None:
    """Deletes key from Redis and in-memory store."""
    try:
        redis = await get_redis_client()
        if redis:
            await redis.delete(key)
    except Exception as e:
        logger.warning(f"Redis delete error for key {key}: {e}")

    _memory_store.pop(key, None)


class OTPService:
    """Coordinates OTP issuance, verification, attempts count, and cooldowns."""

    # -------------------------------------------------------------
    # Registration Email Verification
    # -------------------------------------------------------------
    @classmethod
    async def create_email_verification_otp(cls, email: str) -> Tuple[str, bool, int]:
        """
        Creates an email verification OTP.
        Returns (otp_code, is_created, cooldown_remaining_seconds).
        """
        norm_email = email.lower().strip()
        cd_key = f"{EMAIL_VERIFY_CD_PREFIX}{norm_email}"
        store_key = f"{EMAIL_VERIFY_PREFIX}{norm_email}"

        # Check resend cooldown
        cd_item = await _get_store(cd_key)
        if cd_item:
            remaining = int(cd_item.get("expires_at", 0) - time.time())
            return "", False, max(1, remaining)

        code = generate_six_digit_code()
        hashed = hash_code(code)

        payload = {
            "otp_hash": hashed,
            "attempts": 0,
            "created_at": time.time()
        }

        # Store OTP and cooldown
        await _set_store(store_key, payload, VERIFY_OTP_TTL_SECONDS)
        await _set_store(cd_key, {"expires_at": time.time() + COOLDOWN_TTL_SECONDS}, COOLDOWN_TTL_SECONDS)

        return code, True, 0

    @classmethod
    async def verify_email_otp(cls, email: str, submitted_code: str) -> Tuple[bool, str]:
        """
        Verifies the email verification OTP.
        Returns (success: bool, error_message: str).
        """
        norm_email = email.lower().strip()
        store_key = f"{EMAIL_VERIFY_PREFIX}{norm_email}"

        record = await _get_store(store_key)
        if not record:
            return False, "Verification code has expired or was not requested. Please request a new code."

        attempts = record.get("attempts", 0)
        if attempts >= MAX_ATTEMPTS:
            await _delete_store(store_key)
            return False, "Maximum verification attempts exceeded. Please request a new code."

        if verify_code_hash(submitted_code, record["otp_hash"]):
            # Verification successful -> immediately invalidate OTP
            await _delete_store(store_key)
            return True, ""

        # Invalid code: increment attempt count
        record["attempts"] = attempts + 1
        remaining_attempts = MAX_ATTEMPTS - record["attempts"]

        if remaining_attempts <= 0:
            await _delete_store(store_key)
            return False, "Maximum verification attempts exceeded. Please request a new code."

        # Update attempts in store
        await _set_store(store_key, record, VERIFY_OTP_TTL_SECONDS)
        return False, f"Invalid verification code. {remaining_attempts} attempt{'s' if remaining_attempts != 1 else ''} remaining."

    # -------------------------------------------------------------
    # Forgot Password Reset Code & Token
    # -------------------------------------------------------------
    @classmethod
    async def create_password_reset_code(cls, email: str) -> Tuple[str, bool, int]:
        """
        Creates a password reset code.
        Returns (reset_code, is_created, cooldown_remaining_seconds).
        """
        norm_email = email.lower().strip()
        cd_key = f"{PWD_RESET_CD_PREFIX}{norm_email}"
        store_key = f"{PWD_RESET_PREFIX}{norm_email}"

        # Check resend cooldown
        cd_item = await _get_store(cd_key)
        if cd_item:
            remaining = int(cd_item.get("expires_at", 0) - time.time())
            return "", False, max(1, remaining)

        code = generate_six_digit_code()
        hashed = hash_code(code)

        payload = {
            "otp_hash": hashed,
            "attempts": 0,
            "created_at": time.time()
        }

        await _set_store(store_key, payload, RESET_CODE_TTL_SECONDS)
        await _set_store(cd_key, {"expires_at": time.time() + COOLDOWN_TTL_SECONDS}, COOLDOWN_TTL_SECONDS)

        return code, True, 0

    @classmethod
    async def verify_password_reset_code(cls, email: str, submitted_code: str) -> Tuple[bool, str, Optional[str]]:
        """
        Verifies the 6-digit password reset code.
        If valid, issues a secure one-time reset token valid for 10 minutes.
        Returns (success: bool, message: str, reset_token: Optional[str]).
        """
        norm_email = email.lower().strip()
        store_key = f"{PWD_RESET_PREFIX}{norm_email}"

        record = await _get_store(store_key)
        if not record:
            return False, "Password reset code has expired or was not requested. Please request a new reset code.", None

        attempts = record.get("attempts", 0)
        if attempts >= MAX_ATTEMPTS:
            await _delete_store(store_key)
            return False, "Maximum attempts exceeded. Please request a new reset code.", None

        if verify_code_hash(submitted_code, record["otp_hash"]):
            # Invalidate 6-digit code
            await _delete_store(store_key)

            # Issue a secure one-time reset session token
            reset_token = f"rst_{secrets.token_urlsafe(32)}"
            token_key = f"{PWD_RESET_TOKEN_PREFIX}{reset_token}"
            token_payload = {
                "email": norm_email,
                "issued_at": time.time()
            }
            await _set_store(token_key, token_payload, RESET_CODE_TTL_SECONDS)

            return True, "Reset code verified successfully.", reset_token

        # Invalid code
        record["attempts"] = attempts + 1
        remaining_attempts = MAX_ATTEMPTS - record["attempts"]

        if remaining_attempts <= 0:
            await _delete_store(store_key)
            return False, "Maximum attempts exceeded. Please request a new reset code.", None

        await _set_store(store_key, record, RESET_CODE_TTL_SECONDS)
        return False, f"Invalid reset code. {remaining_attempts} attempt{'s' if remaining_attempts != 1 else ''} remaining.", None

    @classmethod
    async def consume_password_reset_token(cls, email: str, reset_token: str) -> Tuple[bool, str]:
        """
        Validates and consumes the one-time reset token.
        Prevents replay attacks by deleting the token immediately upon validation.
        """
        norm_email = email.lower().strip()
        token_key = f"{PWD_RESET_TOKEN_PREFIX}{reset_token}"

        record = await _get_store(token_key)
        if not record:
            return False, "Invalid or expired password reset session. Please restart password reset."

        stored_email = record.get("email", "").lower().strip()
        if stored_email != norm_email:
            return False, "Reset session does not match the provided email address."

        # Invalidate token immediately (Single-use)
        await _delete_store(token_key)
        return True, ""

    @classmethod
    async def clear_cooldown(cls, email: str) -> None:
        """Clears verification and reset cooldowns for an email (used in test fixtures or administrative reset)."""
        norm_email = email.lower().strip()
        await _delete_store(f"{EMAIL_VERIFY_CD_PREFIX}{norm_email}")
        await _delete_store(f"{PWD_RESET_CD_PREFIX}{norm_email}")
