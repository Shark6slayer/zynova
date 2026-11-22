import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_production_secrets_validation_success():
    """Validates that with valid, distinct, >= 32-char secrets, production config initializes cleanly."""
    valid_jwt = "production_secure_jwt_key_with_at_least_32_characters!"
    valid_otp = "production_secure_otp_hash_key_with_at_least_32_chars!"
    cfg = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=valid_jwt,
        OTP_HASH_SECRET=valid_otp
    )
    assert cfg.JWT_SECRET_KEY == valid_jwt
    assert cfg.OTP_HASH_SECRET == valid_otp


def test_production_secrets_missing_or_empty():
    """Refuses startup if JWT_SECRET_KEY or OTP_HASH_SECRET is missing or empty in production."""
    # Missing OTP_HASH_SECRET
    with pytest.raises(ValidationError) as exc1:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="production_secure_jwt_key_with_at_least_32_characters!",
            OTP_HASH_SECRET=""
        )
    assert "OTP_HASH_SECRET is required" in str(exc1.value)

    # Empty JWT_SECRET_KEY
    with pytest.raises(ValidationError) as exc2:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="   ",
            OTP_HASH_SECRET="production_secure_otp_hash_key_with_at_least_32_chars!"
        )
    assert "JWT_SECRET_KEY is required" in str(exc2.value)


def test_production_secrets_too_short():
    """Refuses startup if either secret is shorter than 32 characters in production."""
    # JWT too short (< 32 chars)
    with pytest.raises(ValidationError) as exc1:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="short_jwt_secret_under_32_ch",
            OTP_HASH_SECRET="production_secure_otp_hash_key_with_at_least_32_chars!"
        )
    assert "must be at least 32 characters" in str(exc1.value)

    # OTP hash secret too short (< 32 chars)
    with pytest.raises(ValidationError) as exc2:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="production_secure_jwt_key_with_at_least_32_characters!",
            OTP_HASH_SECRET="short_otp_secret_key"
        )
    assert "must be at least 32 characters" in str(exc2.value)


def test_production_secrets_equals_old_default():
    """Refuses startup if JWT_SECRET_KEY equals the legacy default string in production."""
    old_default = "super_ai_indic_sovereign_dev_secret_key_change_in_production_2026"
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=old_default,
            OTP_HASH_SECRET="production_secure_otp_hash_key_with_at_least_32_chars!"
        )
    assert "legacy development default key" in str(exc.value)


def test_production_secrets_identical_values():
    """Refuses startup if JWT_SECRET_KEY and OTP_HASH_SECRET have identical values in production."""
    identical = "identically_reused_secret_key_with_over_32_characters!"
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=identical,
            OTP_HASH_SECRET=identical
        )
    assert "cannot have the same value" in str(exc.value)


def test_verification_service_raises_when_otp_hash_secret_missing(monkeypatch):
    """Refuses OTP hash computation when OTP_HASH_SECRET is missing or empty."""
    from app.services.verification_service import (
        compute_registration_otp_hash,
        compute_otp_hash
    )
    from app.core.config import settings

    monkeypatch.setattr(settings, "OTP_HASH_SECRET", None)

    with pytest.raises(RuntimeError) as exc1:
        compute_registration_otp_hash("test@example.com", "123456", "V_ID_1234")
    assert "OTP_HASH_SECRET is required" in str(exc1.value)

    with pytest.raises(RuntimeError) as exc2:
        compute_otp_hash("V_ID_1234", "registration", "123456")
    assert "OTP_HASH_SECRET is required" in str(exc2.value)
