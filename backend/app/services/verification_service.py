"""
ZENOVA — Secure MongoDB Email Verification Model and Repository
Handles 16-character alphanumeric verification_id generation,
HMAC-SHA256 OTP hashing (bound to verification_id, purpose, and OTP),
atomic MongoDB operations, attempt tracking, cooldowns, and single-use consumption.
"""

import hmac
import hashlib
import secrets
import string
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any

from app.core.config import settings
from app.database.client import get_database

logger = logging.getLogger("zenova.verification_service")

# Verification purposes
PURPOSE_REGISTRATION = "registration"
PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_ACCOUNT_RECOVERY = "account_recovery"

# Verification status
STATUS_PENDING = "pending"
STATUS_VERIFIED = "verified"
STATUS_CONSUMED = "consumed"
STATUS_EXPIRED = "expired"
STATUS_FAILED = "failed"

OTP_EXPIRY_MINUTES = 10
VERIFY_OTP_EXPIRATION_MINUTES = OTP_EXPIRY_MINUTES
VERIFY_OTP_COOLDOWN_SECONDS = 60
MAX_VERIFICATION_ATTEMPTS = 5

ALPHANUMERIC_UPPER = string.ascii_uppercase + string.digits


def generate_verification_id() -> str:
    """Generates a cryptographically secure 16-character uppercase alphanumeric verification ID."""
    return "".join(secrets.choice(ALPHANUMERIC_UPPER) for _ in range(16))


def generate_six_digit_otp() -> str:
    """Generates a cryptographically secure 6-digit numeric OTP zero-padded via secrets.randbelow(1_000_000)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def compute_registration_otp_hash(email: str, otp: str, verification_id: str) -> str:
    """
    Computes HMAC-SHA256 hash bound to f"{email}:{otp}:{verification_id}".
    Uses server secret from env (OTP_HASH_SECRET).
    """
    if not settings.OTP_HASH_SECRET:
        raise RuntimeError("OTP_HASH_SECRET is required but not configured.")
    secret = settings.OTP_HASH_SECRET.encode("utf-8")
    message = f"{email.lower().strip()}:{otp.strip()}:{verification_id.strip().upper()}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_registration_otp_hash(email: str, candidate_otp: str, verification_id: str, stored_hash: str) -> bool:
    """Constant-time verification of candidate OTP against stored HMAC hash."""
    expected_hash = compute_registration_otp_hash(email, candidate_otp, verification_id)
    return hmac.compare_digest(expected_hash, stored_hash)


def compute_otp_hash(verification_id: str, purpose: str, otp: str) -> str:
    """
    Computes HMAC-SHA256 hash bound to verification_id, purpose, and the OTP.
    Uses server secret from env (OTP_HASH_SECRET).
    """
    if not settings.OTP_HASH_SECRET:
        raise RuntimeError("OTP_HASH_SECRET is required but not configured.")
    secret = settings.OTP_HASH_SECRET.encode("utf-8")
    message = f"{verification_id}:{purpose}:{otp.strip()}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_otp_hash(verification_id: str, purpose: str, candidate_otp: str, stored_hash: str) -> bool:
    """Constant-time verification of candidate OTP against stored HMAC hash."""
    expected_hash = compute_otp_hash(verification_id, purpose, candidate_otp)
    return hmac.compare_digest(expected_hash, stored_hash)


class VerificationService:
    """
    MongoDB-backed Verification Service providing atomic challenge creation,
    single active challenge enforcement per (email, purpose), atomic attempt tracking,
    and atomic challenge consumption.
    """

    @classmethod
    async def create_verification_challenge(
        cls,
        email: str,
        purpose: str = PURPOSE_REGISTRATION,
        expiration_minutes: int = VERIFY_OTP_EXPIRATION_MINUTES,
        cooldown_seconds: int = VERIFY_OTP_COOLDOWN_SECONDS
    ) -> Tuple[Optional[str], Optional[str], bool, int]:
        """
        Creates or supersedes an active email verification challenge.
        Enforces 60s resend cooldown.
        Atomically supersedes any existing pending challenges for the same (email, purpose).
        Returns: (verification_id, raw_otp, is_created, cooldown_remaining_seconds)
        """
        db = get_database()
        if db is None:
            logger.error("MongoDB unavailable when creating verification challenge")
            return None, None, False, 0

        clean_email = email.lower().strip()
        now = datetime.now(timezone.utc)

        # 1. Check if there is an existing pending challenge under cooldown
        existing = await db.email_verifications.find_one({
            "email": clean_email,
            "purpose": purpose,
            "status": STATUS_PENDING
        }, sort=[("created_at", -1)])

        if existing:
            resend_eligible_at = existing.get("resend_eligible_at")
            if resend_eligible_at:
                if resend_eligible_at.tzinfo is None:
                    resend_eligible_at = resend_eligible_at.replace(tzinfo=timezone.utc)
                if now < resend_eligible_at:
                    cd_remaining = int((resend_eligible_at - now).total_seconds())
                    return existing.get("verification_id"), None, False, max(1, cd_remaining)

            # Invalidate/supersede the previous active challenge atomically
            await db.email_verifications.update_many(
                {
                    "email": clean_email,
                    "purpose": purpose,
                    "status": STATUS_PENDING
                },
                {"$set": {"status": STATUS_EXPIRED, "updated_at": now}}
            )

        # 2. Generate new credentials
        verification_id = generate_verification_id()
        raw_otp = generate_six_digit_otp()
        otp_hash = compute_otp_hash(verification_id, purpose, raw_otp)

        expires_at = now + timedelta(minutes=expiration_minutes)
        resend_eligible_at = now + timedelta(seconds=cooldown_seconds)

        doc = {
            "verification_id": verification_id,
            "email": clean_email,
            "purpose": purpose,
            "otp_hash": otp_hash,
            "status": STATUS_PENDING,
            "attempts": 0,
            "max_attempts": MAX_VERIFICATION_ATTEMPTS,
            "created_at": now,
            "expires_at": expires_at,
            "resend_eligible_at": resend_eligible_at,
            "consumed_at": None,
            "updated_at": now
        }

        await db.email_verifications.insert_one(doc)
        logger.info(f"Created verification challenge for email domain: {clean_email.split('@')[-1]} (purpose: {purpose})")
        return verification_id, raw_otp, True, 0

    @classmethod
    async def verify_otp(
        cls,
        email: str,
        submitted_otp: str,
        purpose: str = PURPOSE_REGISTRATION,
        verification_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Atomically verifies the submitted OTP.
        If verification_id is supplied, look up by verification_id;
        otherwise look up latest pending challenge for (email, purpose).
        Enforces:
        - 5-minute expiration (checked in application logic)
        - Max 5 attempts
        - Constant-time HMAC comparison
        - Atomic status transition to CONSUMED upon success
        - Atomic attempt increment on failure
        Returns: (success: bool, error_message: str, verification_id: Optional[str])
        """
        db = get_database()
        if db is None:
            return False, "Database unavailable", None

        clean_email = email.lower().strip()
        now = datetime.now(timezone.utc)

        query: Dict[str, Any] = {
            "email": clean_email,
            "purpose": purpose,
            "status": STATUS_PENDING
        }
        if verification_id:
            query["verification_id"] = verification_id.strip().upper()

        record = await db.email_verifications.find_one(query, sort=[("created_at", -1)])
        if not record:
            return False, "Verification code has expired or was not requested. Please request a new code.", None

        v_id = record["verification_id"]
        expires_at = record.get("expires_at")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                # Expired: atomically mark expired
                await db.email_verifications.update_one(
                    {"_id": record["_id"], "status": STATUS_PENDING},
                    {"$set": {"status": STATUS_EXPIRED, "updated_at": now}}
                )
                return False, "Verification code has expired. Please request a new code.", v_id

        current_attempts = record.get("attempts", 0)
        max_attempts = record.get("max_attempts", MAX_VERIFICATION_ATTEMPTS)

        if current_attempts >= max_attempts:
            await db.email_verifications.update_one(
                {"_id": record["_id"], "status": STATUS_PENDING},
                {"$set": {"status": STATUS_FAILED, "updated_at": now}}
            )
            return False, "Maximum verification attempts exceeded. Please request a new code.", v_id

        # Constant-time HMAC comparison
        is_valid = verify_otp_hash(v_id, purpose, submitted_otp, record["otp_hash"])

        if is_valid:
            # Atomically consume the verification challenge:
            # Only update if status is still 'pending' to prevent race condition double-consumption
            res = await db.email_verifications.update_one(
                {
                    "_id": record["_id"],
                    "status": STATUS_PENDING
                },
                {
                    "$set": {
                        "status": STATUS_CONSUMED,
                        "consumed_at": now,
                        "updated_at": now
                    }
                }
            )
            if res.modified_count == 1:
                return True, "", v_id
            else:
                return False, "Verification challenge has already been used or modified.", v_id

        # Invalid OTP: atomically increment attempts
        new_attempts = current_attempts + 1
        remaining = max_attempts - new_attempts

        if remaining <= 0:
            # Lock out immediately
            await db.email_verifications.update_one(
                {"_id": record["_id"], "status": STATUS_PENDING},
                {
                    "$set": {
                        "status": STATUS_FAILED,
                        "attempts": new_attempts,
                        "updated_at": now
                    }
                }
            )
            return False, "Maximum verification attempts exceeded. Please request a new code.", v_id

        await db.email_verifications.update_one(
            {"_id": record["_id"], "status": STATUS_PENDING},
            {
                "$set": {
                    "attempts": new_attempts,
                    "updated_at": now
                }
            }
        )
        return False, f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.", v_id

    @classmethod
    async def get_active_challenge(cls, email: str, purpose: str = PURPOSE_REGISTRATION) -> Optional[Dict[str, Any]]:
        """Retrieves the current pending challenge for an email and purpose if not expired."""
        db = get_database()
        if db is None:
            return None
        clean_email = email.lower().strip()
        now = datetime.now(timezone.utc)
        record = await db.email_verifications.find_one({
            "email": clean_email,
            "purpose": purpose,
            "status": STATUS_PENDING
        }, sort=[("created_at", -1)])
        if record:
            expires_at = record.get("expires_at")
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and now <= expires_at:
                return record
        return None
