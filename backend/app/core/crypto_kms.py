import os
import json
import base64
import logging
import hashlib
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from app.core.config import settings
from app.core.security_logger import log_security_event

logger = logging.getLogger("super_ai.kms")

# Key registry: version_id -> 256-bit AES raw bytes
_key_ring: Dict[str, bytes] = {}

def _derive_key_from_secret(secret: str, salt: bytes, info: bytes) -> bytes:
    """Derives a cryptographically strong 256-bit key using HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=info,
    )
    return hkdf.derive(secret.encode("utf-8"))

def initialize_key_management():
    """
    Initializes the cryptographic key ring using the configured KMS/env provider.
    Generates deterministic versioned keys (v1, v2) for testing rotation and active operations.
    """
    global _key_ring
    master_secret = settings.MASTER_ENCRYPTION_KEY or "dev_master_key_super_ai_indic_sovereign_32bytes_sec"
    
    # Derive v1 active key
    salt_v1 = b"super_ai_indic_kms_salt_epoch_1"
    key_v1 = _derive_key_from_secret(master_secret, salt_v1, b"field_encryption_v1")
    _key_ring["v1"] = key_v1

    # Derive v2 rotation key (available for key rotation re-wrapping)
    salt_v2 = b"super_ai_indic_kms_salt_epoch_2"
    key_v2 = _derive_key_from_secret(master_secret, salt_v2, b"field_encryption_v2")
    _key_ring["v2"] = key_v2

    logger.info(f"Initialized Key Management Subsystem (Active Version: {settings.ACTIVE_KEY_VERSION}, Available Versions: {list(_key_ring.keys())})")

# Ensure initialized on import
initialize_key_management()

def encrypt_field(plaintext: str, context: Optional[str] = None, version: Optional[str] = None) -> str:
    """
    Encrypts sensitive text using standard AES-256-GCM authenticated encryption.
    Format: enc:v1:<base64(12-byte IV + ciphertext + 16-byte tag)>
    The context string is bound as Authenticated Additional Data (AAD) to prevent ciphertext transplanting.
    """
    if plaintext is None:
        return ""
    
    ver = version or settings.ACTIVE_KEY_VERSION
    raw_key = _key_ring.get(ver)
    if not raw_key:
        raise ValueError(f"Unknown cryptographic key version: {ver}")

    # Generate 96-bit (12-byte) random nonce per NIST SP 800-38D
    nonce = os.urandom(12)
    aad = context.encode("utf-8") if context else b"super_ai_field_aad"

    aesgcm = AESGCM(raw_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

    # Combined payload: 12-byte nonce + (ciphertext + tag)
    payload = nonce + ciphertext
    b64_payload = base64.urlsafe_b64encode(payload).decode("utf-8")
    return f"enc:{ver}:{b64_payload}"

def decrypt_field(enc_str: str, context: Optional[str] = None) -> str:
    """
    Decrypts AES-256-GCM ciphertext envelope.
    Verifies authentication tag and bound context AAD.
    """
    if not enc_str:
        return ""
    if not is_encrypted(enc_str):
        # Plaintext passthrough if not yet migrated
        return enc_str

    parts = enc_str.split(":", 2)
    if len(parts) != 3 or parts[0] != "enc":
        raise ValueError("Malformed ciphertext envelope format")

    ver = parts[1]
    raw_payload = parts[2]

    raw_key = _key_ring.get(ver)
    if not raw_key:
        log_security_event(
            event_code="CRYPTO_KEY_MISSING",
            action="decrypt_field",
            status="ERROR",
            details={"requested_version": ver}
        )
        raise ValueError(f"Cryptographic key version '{ver}' is not available or has been revoked.")

    try:
        payload = base64.urlsafe_b64decode(raw_payload.encode("utf-8"))
        if len(payload) < 28: # 12-byte nonce + 16-byte auth tag
            raise ValueError("Ciphertext envelope is truncated")

        nonce = payload[:12]
        ciphertext = payload[12:]
        aad = context.encode("utf-8") if context else b"super_ai_field_aad"

        aesgcm = AESGCM(raw_key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        log_security_event(
            event_code="CRYPTO_DECRYPT_FAILURE",
            action="decrypt_field",
            status="BLOCKED",
            details={"version": ver, "error": "Integrity check failed (tag mismatch or wrong key)"}
        )
        raise ValueError("Decryption failed: integrity check failed or wrong cryptographic key.")

def is_encrypted(val: Any) -> bool:
    """Returns True if the string follows the envelope format enc:<version>:<b64>."""
    if not isinstance(val, str):
        return False
    return val.startswith("enc:v") and len(val.split(":")) == 3

def rotate_field_encryption(enc_str: str, target_version: str, context: Optional[str] = None) -> str:
    """Re-encrypts ciphertext under a newer key version without exposing plaintext outside memory."""
    plaintext = decrypt_field(enc_str, context=context)
    return encrypt_field(plaintext, context=context, version=target_version)

def get_kms_health() -> Dict[str, Any]:
    """Returns cryptographic subsystem operational telemetry without leaking secret key values."""
    return {
        "status": "operational",
        "provider": settings.KMS_PROVIDER,
        "active_version": settings.ACTIVE_KEY_VERSION,
        "supported_versions": list(_key_ring.keys()),
        "primitive": "AES-256-GCM (NIST SP 800-38D)",
        "kdf": "HKDF-SHA256 (RFC 5869)"
    }
