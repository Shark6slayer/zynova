# SUPER_AI AUDIT LEDGER SCHEMA SPECIFICATION (v1.0.0)

**Project:** SUPER_AI (`C:\super_ai`)  
**Schema Identifier:** `urn:superai:ledger:event:1.0.0`  
**Status:** Implemented (Phase 10)  

---

## 1. Overview

The SUPER_AI Private Cryptographic Audit Ledger provides an append-only, tamper-evident log for critical security, authentication, and state-transition events. The ledger is designed to be self-verifying, independent of application databases, and structured for future anchoring into public decentralized blockchains.

---

## 2. Event Body Schema & Field Constraints

Every ledger record conforms to the following strict JSON schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SuperAIAuditLedgerEvent",
  "type": "object",
  "required": [
    "schema_version",
    "sequence",
    "timestamp",
    "event_type",
    "actor_pseudonym",
    "metadata",
    "prev_hash",
    "current_hash"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0.0",
      "description": "Semantic version of the ledger schema."
    },
    "sequence": {
      "type": "integer",
      "minimum": 1,
      "description": "Monotonically increasing integer sequence number assigned atomically via counter."
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp (YYYY-MM-DDTHH:MM:SS.mmmmmm+00:00 or with trailing Z)."
    },
    "event_type": {
      "type": "string",
      "enum": [
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
      ],
      "description": "Enumerated category of security-relevant event."
    },
    "actor_pseudonym": {
      "type": ["string", "null"],
      "pattern": "^(pseudo:[a-f0-9]{24}|anonymous|system)$",
      "description": "HMAC-SHA256 salted pseudonym of actor; null/anonymous if unauthenticated."
    },
    "metadata": {
      "type": "object",
      "description": "Minimal non-sensitive context dictionary. Forbidden keys (passwords, tokens, PAN, etc.) are strictly rejected at the schema level."
    },
    "prev_hash": {
      "type": "string",
      "pattern": "^[a-f0-9]{64}$",
      "description": "64-character lowercase hexadecimal SHA-256 hash of the immediate preceding event (Genesis hash is 64 zeros)."
    },
    "current_hash": {
      "type": "string",
      "pattern": "^[a-f0-9]{64}$",
      "description": "64-character lowercase hexadecimal SHA-256 hash computed over canonical JSON of all event fields except current_hash."
    }
  },
  "additionalProperties": false
}
```

---

## 3. Deterministic Canonical Serialization (RFC 8785 / JCS)

To ensure hash stability across different languages, platforms, and database drivers:

1. **Hashable Payload:**  
   The `current_hash` is computed over the canonical serialization of the 7 body fields:
   ```json
   {
     "actor_pseudonym": "...",
     "event_type": "...",
     "metadata": {...},
     "prev_hash": "...",
     "schema_version": "1.0.0",
     "sequence": 1,
     "timestamp": "..."
   }
   ```
2. **Canonical JSON Rules:**
   - Keys must be sorted lexicographically by Unicode code points.
   - Separators must strictly omit whitespace: `","` (comma) and `":"` (colon).
   - Character encoding: UTF-8 without Byte Order Mark (BOM).
   - Floating point formatting must not contain trailing decimal zeroes or IEEE-754 NaN/Infinity values.
3. **Hash Algorithm:**
   $$\text{current\_hash} = \text{SHA-256}(\text{JCS}(\text{EventBody}))$$

---

## 4. Genesis Event Definition

The first event in the ledger ($N=1$) must link to the Genesis Hash:
```
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
```

---

## 5. Checkpoint Schema & Signature Specification

Periodic checkpoints capture the state of the ledger up to `end_sequence`:

```json
{
  "checkpoint_version": "1.0.0",
  "end_sequence": 100,
  "end_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "public_key": "7d9b9...32-byte-hex",
  "timestamp": "2026-10-16T00:00:00.000000+00:00",
  "signature": "c8f2...64-byte-hex-ed25519-signature"
}
```

### Signature Computation:
$$\text{Signature} = \text{Ed25519\_Sign}(\text{PrivateKey}, \text{JCS}(\text{CheckpointBody}))$$
where $\text{CheckpointBody}$ excludes the `signature` and `created_at` fields.
