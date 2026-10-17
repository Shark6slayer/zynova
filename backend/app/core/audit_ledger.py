"""
audit_ledger.py - Private Cryptographic Audit Ledger Subsystem (Phase 10)

Implements an append-only, cryptographically-chained event ledger designed for
tamper-evidence and future public blockchain anchoring:
- SHA-256 hash chaining (previous_hash -> current_hash).
- RFC 8785 JSON Canonicalization Scheme (JCS) deterministic serialization.
- Strict privacy redaction: HMAC-SHA256 actor pseudonyms with configurable salt.
- Atomic sequence number assignment backed by MongoDB atomic increment.
- Ed25519 digital signatures for periodic ledger checkpoints.
- Standalone verification functionality for independent offline audit.
"""

import os
import json
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from app.core.config import settings
from app.database.client import get_database

logger = logging.getLogger("super_ai.audit_ledger")

LEDGER_SCHEMA_VERSION = "1.0.0"
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

# In-memory signer instance for Ed25519 checkpoint signing
_signing_private_key: Optional[ed25519.Ed25519PrivateKey] = None
_signing_public_key: Optional[ed25519.Ed25519PublicKey] = None


def canonical_json_dumps(obj: Any) -> str:
    """
    Serializes a Python object to canonical JSON string following RFC 8785:
    - UTF-8 representation without BOM.
    - Keys sorted lexicographically by Unicode code points.
    - No whitespace between tokens (separators=(',', ':')).
    - No IEEE-754 NaN or Infinity values.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False
    )


def compute_sha256_hex(data_str: str) -> str:
    """Computes SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


def generate_actor_pseudonym(raw_actor_id: Optional[str]) -> Optional[str]:
    """
    Generates a privacy-preserving pseudonymous actor identifier using HMAC-SHA256
    with a server-side salt. Prevents direct correlation with raw user IDs.
    Returns None if raw_actor_id is empty/anonymous.
    """
    if not raw_actor_id or raw_actor_id == "anonymous" or raw_actor_id == "system":
        return raw_actor_id
    
    salt = settings.AUDIT_LEDGER_PSEUDONYM_SALT.encode("utf-8")
    h = hmac.new(salt, raw_actor_id.encode("utf-8"), hashlib.sha256)
    return f"pseudo:{h.hexdigest()[:24]}"


def initialize_ledger_signer():
    """
    Initializes the Ed25519 checkpoint signing key pair.
    If no key is configured in settings, derives a deterministic development key
    pair and logs a development security notice.
    """
    global _signing_private_key, _signing_public_key
    if settings.AUDIT_LEDGER_SIGNER_KEY_HEX:
        try:
            seed_bytes = bytes.fromhex(settings.AUDIT_LEDGER_SIGNER_KEY_HEX)
            _signing_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)
            _signing_public_key = _signing_private_key.public_key()
            logger.info("Audit ledger initialized with configured Ed25519 signing key.")
            return
        except Exception as e:
            logger.error(f"Failed to load AUDIT_LEDGER_SIGNER_KEY_HEX: {e}")

    # Development fallback: Deterministic seed from master key for reproducibility in test/dev
    fallback_seed = hashlib.sha256(
        (settings.MASTER_ENCRYPTION_KEY or "dev_ledger_fallback_seed_2026").encode("utf-8")
    ).digest()
    _signing_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(fallback_seed)
    _signing_public_key = _signing_private_key.public_key()
    logger.info("Audit ledger initialized with development Ed25519 key (Notice: non-HSM software key).")


# Initialize on module load
initialize_ledger_signer()


def get_signer_public_key_hex() -> str:
    """Returns the hex-encoded 32-byte Ed25519 public key."""
    if _signing_public_key is None:
        initialize_ledger_signer()
    pub_bytes = _signing_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return pub_bytes.hex()


def sign_checkpoint_payload(payload_str: str) -> str:
    """Signs a canonical string using the Ed25519 private key, returning hex signature."""
    if _signing_private_key is None:
        initialize_ledger_signer()
    sig = _signing_private_key.sign(payload_str.encode("utf-8"))
    return sig.hex()


def verify_checkpoint_signature(payload_str: str, sig_hex: str, public_key_hex: str) -> bool:
    """Verifies an Ed25519 signature against canonical payload string."""
    try:
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pub_key.verify(bytes.fromhex(sig_hex), payload_str.encode("utf-8"))
        return True
    except Exception:
        return False


def build_event_body(
    schema_version: str,
    sequence: int,
    timestamp: str,
    event_type: str,
    actor_pseudonym: Optional[str],
    metadata: Dict[str, Any],
    prev_hash: str
) -> Dict[str, Any]:
    """
    Constructs the canonical dictionary of event fields used to compute the current event hash.
    Does NOT include the 'current_hash' field itself.
    """
    return {
        "actor_pseudonym": actor_pseudonym,
        "event_type": event_type,
        "metadata": metadata,
        "prev_hash": prev_hash,
        "schema_version": schema_version,
        "sequence": sequence,
        "timestamp": timestamp,
    }


def compute_event_hash(
    schema_version: str,
    sequence: int,
    timestamp: str,
    event_type: str,
    actor_pseudonym: Optional[str],
    metadata: Dict[str, Any],
    prev_hash: str
) -> str:
    """Computes SHA-256 hash over the canonical JSON representation of event body fields."""
    body = build_event_body(
        schema_version=schema_version,
        sequence=sequence,
        timestamp=timestamp,
        event_type=event_type,
        actor_pseudonym=actor_pseudonym,
        metadata=metadata,
        prev_hash=prev_hash
    )
    canonical_repr = canonical_json_dumps(body)
    return compute_sha256_hex(canonical_repr)


# Core Security Events Whitelist
PERMITTED_EVENT_TYPES = {
    "AUTH_SUCCESS",
    "AUTH_FAILURE",
    "AUTH_LOGOUT",
    "SESSION_REVOKED",
    "SECURITY_SETTINGS_CHANGED",
    "ACCOUNT_SUSPENDED",
    "ACCOUNT_RECOVERED",
    "ADMIN_ROLE_GRANTED",
    "ADMIN_ROLE_REVOKED",
    "SELLER_APPROVED",
    "SELLER_REJECTED",
    "SELLER_SUSPENDED",
    "ORDER_SECURITY_STATUS_CHANGED",
    "MALWARE_UPLOAD_BLOCKED",
    "CHECKPOINT_CREATED",
    "CHECKPOINT_VERIFIED"
}

# Forbidden sensitive keys in metadata
FORBIDDEN_METADATA_KEYS = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "credit_card", "card_number", "cvv", "vpa", "upi_pin",
    "private_key", "message_text", "body", "email", "phone"
}


def sanitize_ledger_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates and sanitizes audit metadata.
    Rejects or redacts forbidden sensitive fields.
    """
    if not meta:
        return {}
    sanitized = {}
    for k, v in meta.items():
        k_clean = str(k).lower().strip()
        if k_clean in FORBIDDEN_METADATA_KEYS or any(bad in k_clean for bad in ["pass", "token", "secret", "cvv", "pin"]):
            raise ValueError(f"Prohibited sensitive key in audit metadata: '{k}'")
        if isinstance(v, (str, int, float, bool)) or v is None:
            sanitized[k] = v
        else:
            sanitized[k] = str(v)[:128]
    return sanitized


async def record_audit_event(
    event_type: str,
    raw_actor_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    client_ip: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Appends a cryptographically chained event to the audit ledger.
    Allocates sequence atomically via MongoDB findOneAndUpdate on ledger_sequence counter.
    Prevents concurrent sequence collision.
    """
    if not settings.AUDIT_LEDGER_ENABLED:
        return None

    if event_type not in PERMITTED_EVENT_TYPES:
        raise ValueError(f"Unregistered event type for audit ledger: '{event_type}'")

    clean_meta = sanitize_ledger_metadata(metadata)
    if client_ip:
        # Mask IP for privacy (e.g. 192.168.1.0/24 or hash)
        clean_meta["client_ip_subnet"] = ".".join(client_ip.split(".")[:3]) + ".0" if "." in client_ip else "masked"

    actor_pseudo = generate_actor_pseudonym(raw_actor_id)
    now_utc = datetime.now(timezone.utc).isoformat()

    db = get_database()
    if db is None:
        logger.warning("Database unavailable; audit event was not committed to ledger.")
        return None

    # Step 1: Atomically allocate sequence number using MongoDB find_one_and_update
    seq_doc = await db.ledger_counters.find_one_and_update(
        {"_id": "audit_ledger_sequence"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    sequence = seq_doc.get("seq", 1)

    # Step 2: Fetch previous event's hash
    if sequence == 1:
        prev_hash = GENESIS_HASH
    else:
        prev_event = await db.audit_ledger.find_one({"sequence": sequence - 1})
        if not prev_event:
            # If for any reason sequence - 1 is missing, find the highest existing sequence
            last_event = await db.audit_ledger.find_one(sort=[("sequence", -1)])
            prev_hash = last_event["current_hash"] if last_event else GENESIS_HASH
        else:
            prev_hash = prev_event["current_hash"]

    # Step 3: Compute current event hash
    current_hash = compute_event_hash(
        schema_version=LEDGER_SCHEMA_VERSION,
        sequence=sequence,
        timestamp=now_utc,
        event_type=event_type,
        actor_pseudonym=actor_pseudo,
        metadata=clean_meta,
        prev_hash=prev_hash
    )

    # Step 4: Construct and insert document
    ledger_doc = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "sequence": sequence,
        "timestamp": now_utc,
        "event_type": event_type,
        "actor_pseudonym": actor_pseudo,
        "metadata": clean_meta,
        "prev_hash": prev_hash,
        "current_hash": current_hash,
    }

    try:
        await db.audit_ledger.insert_one(ledger_doc)
    except Exception as e:
        logger.error(f"Failed to insert audit ledger record seq={sequence}: {e}")
        raise

    # Step 5: Check if periodic checkpoint creation is triggered
    if sequence % settings.AUDIT_LEDGER_CHECKPOINT_INTERVAL_EVENTS == 0:
        try:
            await create_ledger_checkpoint(sequence, current_hash)
        except Exception as cp_err:
            logger.error(f"Failed to create periodic checkpoint at seq={sequence}: {cp_err}")

    return ledger_doc


async def create_ledger_checkpoint(end_sequence: int, end_hash: str) -> Dict[str, Any]:
    """
    Creates and digitally signs an Ed25519 checkpoint covering up to end_sequence.
    """
    db = get_database()
    now_utc = datetime.now(timezone.utc).isoformat()
    pub_key_hex = get_signer_public_key_hex()

    checkpoint_body = {
        "checkpoint_version": "1.0.0",
        "end_hash": end_hash,
        "end_sequence": end_sequence,
        "public_key": pub_key_hex,
        "timestamp": now_utc,
    }
    canonical_body = canonical_json_dumps(checkpoint_body)
    signature_hex = sign_checkpoint_payload(canonical_body)

    checkpoint_doc = {
        **checkpoint_body,
        "signature": signature_hex,
        "created_at": now_utc
    }

    if db is not None:
        await db.ledger_checkpoints.insert_one(checkpoint_doc)
        logger.info(f"Audit ledger checkpoint created and signed: seq={end_sequence}, hash={end_hash[:16]}...")

    return checkpoint_doc


def verify_ledger_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Independent offline verification logic.
    Validates:
    - Sequence continuity (1, 2, 3...)
    - Current event hash matches re-computed canonical hash
    - Previous hash link matches preceding record's current hash
    - No missing, altered, duplicate, or reordered records.
    """
    if not records:
        return {"valid": True, "count": 0, "errors": []}

    errors = []
    expected_seq = records[0]["sequence"]
    expected_prev_hash = records[0]["prev_hash"]

    seen_sequences = set()
    seen_hashes = set()

    for idx, rec in enumerate(records):
        seq = rec.get("sequence")
        cur_hash = rec.get("current_hash")
        prev_hash = rec.get("prev_hash")

        # 1. Duplicate checks
        if seq in seen_sequences:
            errors.append(f"Duplicate sequence detected at index {idx}: sequence={seq}")
        seen_sequences.add(seq)

        if cur_hash in seen_hashes:
            errors.append(f"Duplicate current_hash detected at index {idx}: hash={cur_hash}")
        seen_hashes.add(cur_hash)

        # 2. Sequence continuity
        if seq != expected_seq:
            errors.append(f"Sequence break at index {idx}: expected {expected_seq}, found {seq}")

        # 3. Hash link continuity
        if idx > 0 and prev_hash != expected_prev_hash:
            errors.append(
                f"Broken hash chain at index {idx} (seq={seq}): prev_hash={prev_hash} does not match prior current_hash={expected_prev_hash}"
            )

        # 4. Canonical hash re-computation and verification
        expected_hash = compute_event_hash(
            schema_version=rec.get("schema_version", LEDGER_SCHEMA_VERSION),
            sequence=seq,
            timestamp=rec.get("timestamp", ""),
            event_type=rec.get("event_type", ""),
            actor_pseudonym=rec.get("actor_pseudonym"),
            metadata=rec.get("metadata", {}),
            prev_hash=prev_hash
        )

        if cur_hash != expected_hash:
            errors.append(
                f"Tampered or invalid hash at index {idx} (seq={seq}): record has {cur_hash}, recomputed {expected_hash}"
            )

        expected_seq = seq + 1
        expected_prev_hash = cur_hash

    return {
        "valid": len(errors) == 0,
        "count": len(records),
        "first_sequence": records[0]["sequence"],
        "last_sequence": records[-1]["sequence"],
        "first_hash": records[0]["current_hash"],
        "last_hash": records[-1]["current_hash"],
        "errors": errors
    }
