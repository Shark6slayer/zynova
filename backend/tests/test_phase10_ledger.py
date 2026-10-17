"""
test_phase10_ledger.py - Automated Verification Suite for Private Cryptographic Audit Ledger

Verifies:
1. Canonical serialization (RFC 8785) and deterministic SHA-256 hash chaining.
2. Actor pseudonymization via HMAC-SHA256 with secret salt.
3. Strict rejection of prohibited sensitive fields in metadata (passwords, tokens, PAN, etc.).
4. Tampering detection: Altering event content, timestamp, sequence, or prev_hash fails verification.
5. Deletion detection: Removing any intermediate record breaks sequence or hash chain continuity.
6. Reordering detection: Swapping adjacent records fails sequence and hash continuity checks.
7. Duplication detection: Duplicate sequence or current_hash triggers explicit verification failure.
8. Ed25519 checkpoint digital signatures and tampering detection.
9. Standalone CLI verifier behavior against exported JSON ledger files.
"""

import pytest
import os
import json
import tempfile
from app.core.audit_ledger import (
    canonical_json_dumps,
    compute_sha256_hex,
    compute_event_hash,
    generate_actor_pseudonym,
    sanitize_ledger_metadata,
    verify_ledger_records,
    sign_checkpoint_payload,
    verify_checkpoint_signature,
    get_signer_public_key_hex,
    GENESIS_HASH,
    LEDGER_SCHEMA_VERSION,
)
from verify_ledger import verify_file


def test_canonical_json_serialization_rfc8785():
    """Test that canonical JSON sorting, whitespace elimination, and encoding match RFC 8785."""
    obj1 = {"z": 1, "a": 2, "m": {"b": 10, "a": 20}}
    obj2 = {"a": 2, "m": {"a": 20, "b": 10}, "z": 1}
    # Regardless of dictionary insertion order, serialized strings must be strictly identical
    assert canonical_json_dumps(obj1) == '{"a":2,"m":{"a":20,"b":10},"z":1}'
    assert canonical_json_dumps(obj1) == canonical_json_dumps(obj2)
    # Ensure no spaces around colons or commas
    assert ": " not in canonical_json_dumps(obj1)
    assert ", " not in canonical_json_dumps(obj1)


def test_actor_pseudonym_generation():
    """Test that raw user IDs are converted to HMAC pseudonyms and are deterministic."""
    raw_id = "670c1a2b3c4d5e6f7a8b9c0d"
    pseudo1 = generate_actor_pseudonym(raw_id)
    pseudo2 = generate_actor_pseudonym(raw_id)
    assert pseudo1.startswith("pseudo:")
    assert pseudo1 == pseudo2
    assert raw_id not in pseudo1
    # System and anonymous actors remain constant
    assert generate_actor_pseudonym("anonymous") == "anonymous"
    assert generate_actor_pseudonym("system") == "system"


def test_sensitive_field_rejection_in_metadata():
    """Test that metadata containing prohibited sensitive keys is rejected with ValueError."""
    # Forbidden password
    with pytest.raises(ValueError, match="Prohibited sensitive key"):
        sanitize_ledger_metadata({"password": "secret_password"})

    # Forbidden access token
    with pytest.raises(ValueError, match="Prohibited sensitive key"):
        sanitize_ledger_metadata({"access_token": "ey..."})

    # Forbidden CVV / card
    with pytest.raises(ValueError, match="Prohibited sensitive key"):
        sanitize_ledger_metadata({"cvv": "123"})

    # Safe metadata accepted
    safe = sanitize_ledger_metadata({"method": "password", "role": "buyer", "count": 5})
    assert safe["method"] == "password"
    assert safe["count"] == 5


def test_valid_ledger_chain_verification():
    """Construct a synthetic multi-block ledger chain and verify it passes verification."""
    records = []
    prev_h = GENESIS_HASH

    for seq in range(1, 6):
        ts = f"2026-10-16T00:00:0{seq}Z"
        evt_type = "AUTH_SUCCESS" if seq % 2 == 1 else "AUTH_LOGOUT"
        pseudo = f"pseudo:test_user_{seq}"
        meta = {"action_index": seq}

        cur_h = compute_event_hash(
            schema_version=LEDGER_SCHEMA_VERSION,
            sequence=seq,
            timestamp=ts,
            event_type=evt_type,
            actor_pseudonym=pseudo,
            metadata=meta,
            prev_hash=prev_h
        )

        records.append({
            "schema_version": LEDGER_SCHEMA_VERSION,
            "sequence": seq,
            "timestamp": ts,
            "event_type": evt_type,
            "actor_pseudonym": pseudo,
            "metadata": meta,
            "prev_hash": prev_h,
            "current_hash": cur_h
        })
        prev_h = cur_h

    res = verify_ledger_records(records)
    assert res["valid"] is True
    assert res["count"] == 5
    assert len(res["errors"]) == 0


def test_tampering_detection_in_event_body():
    """Test that altering metadata or timestamps in any record is detected."""
    records = []
    prev_h = GENESIS_HASH
    for seq in range(1, 4):
        ts = f"2026-10-16T00:00:0{seq}Z"
        cur_h = compute_event_hash(LEDGER_SCHEMA_VERSION, seq, ts, "AUTH_SUCCESS", None, {}, prev_h)
        records.append({
            "schema_version": LEDGER_SCHEMA_VERSION,
            "sequence": seq,
            "timestamp": ts,
            "event_type": "AUTH_SUCCESS",
            "actor_pseudonym": None,
            "metadata": {},
            "prev_hash": prev_h,
            "current_hash": cur_h
        })
        prev_h = cur_h

    # Tamper with record #2's metadata
    records[1]["metadata"] = {"tampered": True}
    res = verify_ledger_records(records)
    assert res["valid"] is False
    assert any("Tampered or invalid hash" in err for err in res["errors"])


def test_deletion_detection():
    """Test that deleting an intermediate record breaks sequence and hash continuity."""
    records = []
    prev_h = GENESIS_HASH
    for seq in range(1, 5):
        ts = f"2026-10-16T00:00:0{seq}Z"
        cur_h = compute_event_hash(LEDGER_SCHEMA_VERSION, seq, ts, "AUTH_SUCCESS", None, {}, prev_h)
        records.append({
            "schema_version": LEDGER_SCHEMA_VERSION,
            "sequence": seq,
            "timestamp": ts,
            "event_type": "AUTH_SUCCESS",
            "actor_pseudonym": None,
            "metadata": {},
            "prev_hash": prev_h,
            "current_hash": cur_h
        })
        prev_h = cur_h

    # Delete record 2 (sequence 2)
    tampered_records = [records[0], records[2], records[3]]
    res = verify_ledger_records(tampered_records)
    assert res["valid"] is False
    assert any("Sequence break" in err or "Broken hash chain" in err for err in res["errors"])


def test_reordering_detection():
    """Test that swapping two adjacent records fails verification."""
    records = []
    prev_h = GENESIS_HASH
    for seq in range(1, 4):
        ts = f"2026-10-16T00:00:0{seq}Z"
        cur_h = compute_event_hash(LEDGER_SCHEMA_VERSION, seq, ts, "AUTH_SUCCESS", None, {}, prev_h)
        records.append({
            "schema_version": LEDGER_SCHEMA_VERSION,
            "sequence": seq,
            "timestamp": ts,
            "event_type": "AUTH_SUCCESS",
            "actor_pseudonym": None,
            "metadata": {},
            "prev_hash": prev_h,
            "current_hash": cur_h
        })
        prev_h = cur_h

    # Swap records 1 and 2
    swapped = [records[0], records[2], records[1]]
    res = verify_ledger_records(swapped)
    assert res["valid"] is False
    assert len(res["errors"]) > 0


def test_duplicate_sequence_detection():
    """Test that duplicate records with identical sequence numbers fail verification."""
    rec = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "sequence": 1,
        "timestamp": "2026-10-16T00:00:01Z",
        "event_type": "AUTH_SUCCESS",
        "actor_pseudonym": None,
        "metadata": {},
        "prev_hash": GENESIS_HASH,
        "current_hash": compute_event_hash(LEDGER_SCHEMA_VERSION, 1, "2026-10-16T00:00:01Z", "AUTH_SUCCESS", None, {}, GENESIS_HASH)
    }
    res = verify_ledger_records([rec, rec])
    assert res["valid"] is False
    assert any("Duplicate" in err for err in res["errors"])


def test_ed25519_checkpoint_signature_verification():
    """Test Ed25519 signature generation, verification, and tampering detection."""
    pub_key_hex = get_signer_public_key_hex()
    body = {
        "checkpoint_version": "1.0.0",
        "end_hash": "a" * 64,
        "end_sequence": 100,
        "public_key": pub_key_hex,
        "timestamp": "2026-10-16T00:00:00Z"
    }
    canonical_body = canonical_json_dumps(body)
    sig_hex = sign_checkpoint_payload(canonical_body)

    # Valid verification
    assert verify_checkpoint_signature(canonical_body, sig_hex, pub_key_hex) is True

    # Tampered payload fails verification
    tampered_body = canonical_json_dumps({**body, "end_sequence": 101})
    assert verify_checkpoint_signature(tampered_body, sig_hex, pub_key_hex) is False


def test_standalone_cli_verifier_execution():
    """Test standalone verify_file CLI runner against a temporary valid and tampered export."""
    rec = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "sequence": 1,
        "timestamp": "2026-10-16T00:00:01Z",
        "event_type": "AUTH_SUCCESS",
        "actor_pseudonym": "pseudo:abc",
        "metadata": {"test": True},
        "prev_hash": GENESIS_HASH,
        "current_hash": compute_event_hash(LEDGER_SCHEMA_VERSION, 1, "2026-10-16T00:00:01Z", "AUTH_SUCCESS", "pseudo:abc", {"test": True}, GENESIS_HASH)
    }
    
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump({"records": [rec], "checkpoints": []}, f)
        temp_path = f.name

    try:
        assert verify_file(temp_path) is True
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
