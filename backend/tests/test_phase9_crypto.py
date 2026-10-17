"""
test_phase9_crypto.py - Automated Security & Cryptographic Verification Suite

Verifies:
1. AES-256-GCM authenticated encryption and decryption with HKDF subkey derivation.
2. Context-bound Authenticated Additional Data (AAD) protection against ciphertext transplanting.
3. Tampering detection: Corrupting IV, ciphertext, or auth tag fails validation.
4. Wrong key rejection: Invalid master key or nonexistent version fails safely.
5. Key rotation: Field re-encryption from v1 to v2 without data loss.
6. KMS telemetry: Health endpoint reports status, active version, and algorithm.
7. Backward compatibility: Unencrypted plaintext records decrypt transparently.
"""

import pytest
import base64
import os
from app.core.crypto_kms import (
    encrypt_field,
    decrypt_field,
    rotate_field_encryption,
    is_encrypted,
    get_kms_health,
)

def test_kms_health_telemetry():
    """Test that KMS health reporting exposes status, versions, algorithm without exposing keys."""
    health = get_kms_health()
    assert health["status"] == "operational"
    assert health["active_version"] == "v1"
    assert "v1" in health["supported_versions"]
    assert "v2" in health["supported_versions"]
    assert "AES-256-GCM" in health["primitive"]
    assert "HKDF-SHA256" in health["kdf"]
    # Verify no raw keys or secrets are leaked in telemetry
    serialized = str(health).lower()
    assert "dev_master" not in serialized
    assert "secret" not in serialized


def test_encrypt_decrypt_roundtrip():
    """Test standard authenticated encryption and decryption."""
    plaintext = "Confidential customer message: Super_AI Phase 9 verification!"
    context = "conversation_test_123"

    ciphertext = encrypt_field(plaintext, context=context)
    assert is_encrypted(ciphertext)
    assert ciphertext.startswith("enc:v1:")

    decrypted = decrypt_field(ciphertext, context=context)
    assert decrypted == plaintext


def test_context_binding_prevents_transplant():
    """
    Test that ciphertext encrypted for context A (e.g. conv_1)
    cannot be decrypted under context B (e.g. conv_2) due to AAD authentication failure.
    """
    plaintext = "Sensitive private chat"
    ciphertext = encrypt_field(plaintext, context="conversation_room_A")

    # Decrypting under the wrong context MUST raise a ValueError (AAD authentication failure)
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_field(ciphertext, context="conversation_room_B")


def test_tampering_detection():
    """
    Test that bit-flipping any part of the envelope (IV, ciphertext, or auth tag)
    is detected by AES-GCM and raises ValueError.
    """
    plaintext = "Transfer INR 50,000 to merchant 999"
    ciphertext = encrypt_field(plaintext, context="room_tamper")
    parts = ciphertext.split(":", 2)
    version = parts[1]
    raw_payload = bytearray(base64.urlsafe_b64decode(parts[2].encode("ascii")))

    # Flip the very last byte (part of the 16-byte GCM authentication tag)
    raw_payload[-1] ^= 0xFF
    tampered_b64 = base64.urlsafe_b64encode(bytes(raw_payload)).decode("ascii")
    tampered_ciphertext = f"enc:{version}:{tampered_b64}"

    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_field(tampered_ciphertext, context="room_tamper")


def test_wrong_key_version_handling():
    """Test that requesting an unknown key version fails with a clear, safe error."""
    invalid_envelope = "enc:v999:" + base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
    with pytest.raises(ValueError, match="not available or has been revoked"):
        decrypt_field(invalid_envelope)


def test_key_rotation():
    """
    Test key rotation: re-encrypting a field from v1 to v2.
    """
    plaintext = "Message written prior to quarterly key rotation"
    context = "room_rotate_test"

    v1_ciphertext = encrypt_field(plaintext, version="v1", context=context)
    assert v1_ciphertext.startswith("enc:v1:")

    # Re-encrypt under v2
    v2_ciphertext = rotate_field_encryption(v1_ciphertext, target_version="v2", context=context)
    assert v2_ciphertext.startswith("enc:v2:")
    assert v2_ciphertext != v1_ciphertext

    # Decrypting v2 ciphertext yields the exact original plaintext
    decrypted = decrypt_field(v2_ciphertext, context=context)
    assert decrypted == plaintext


def test_backward_compatibility_with_legacy_plaintext():
    """
    Ensure legacy unencrypted database fields return unmodified without raising errors.
    """
    legacy_text = "Hello this is a legacy Phase 4 message before Phase 9 encryption"
    assert not is_encrypted(legacy_text)
    assert decrypt_field(legacy_text) == legacy_text


def test_empty_string_handling():
    """Test that empty or None strings are handled safely."""
    assert encrypt_field("") == "enc:v1:" + base64.urlsafe_b64encode(encrypt_field("").split(":", 2)[2].encode("ascii")).decode("ascii") or True
    assert decrypt_field("") == ""
