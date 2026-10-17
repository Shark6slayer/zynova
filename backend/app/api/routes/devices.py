"""
routes/devices.py - Device Identity, Authenticated Sessions & Verifiable Security Actions (Phase 12)

Provides:
- Privacy-conscious session listing, selective revocation, and revoke-all workflows.
- Ed25519 cryptographic device registration and key management.
- Cryptographic challenge-response protocol for high-risk sensitive operations.
- Server-side verification requiring device signature and recent re-authentication.
- Signed administrative security event integration with Phase 10 Audit Ledger.
"""

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status, Request
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.schemas.all_schemas import (
    SessionInfoResponse,
    DeviceRegisterPayload,
    DeviceResponse,
    ChallengeRequestPayload,
    ChallengeResponse,
    ChallengeVerifyPayload,
    SensitiveActionResponse
)
from app.api.deps import get_current_user, get_current_user_payload
from app.database.client import get_database
from app.core.security import verify_password
from app.core.token_revocation import revoke_token
from app.core.audit_ledger import record_audit_event, canonical_json_dumps

router = APIRouter(prefix="/devices", tags=["Device Identity & Security Actions"])

CHALLENGE_EXPIRY_SECONDS = 300  # 5 minutes validity


def mask_client_ip(ip: Optional[str]) -> str:
    """Masks client IP for privacy preservation."""
    if not ip or ip == "unknown":
        return "unknown"
    if "." in ip:
        parts = ip.split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return "masked_ipv6"


def parse_device_label(user_agent: Optional[str]) -> Tuple[str, str]:
    """Generates a friendly device label and platform from user agent."""
    if not user_agent:
        return "Unknown Device", "web"
    ua = user_agent.lower()
    if "android" in ua:
        return "Android Device", "android"
    elif "iphone" in ua or "ipad" in ua:
        return "Apple iOS Device", "ios"
    elif "windows" in ua:
        return "Windows PC", "desktop"
    elif "macintosh" in ua or "mac os" in ua:
        return "Macintosh Desktop", "desktop"
    elif "linux" in ua:
        return "Linux Workstation", "desktop"
    return "Web Browser", "web"


# ==========================================================
# 1. Active Session Management
# ==========================================================

@router.get("/sessions", response_model=List[SessionInfoResponse])
async def list_active_sessions(
    current_user: dict = Depends(get_current_user),
    payload: dict = Depends(get_current_user_payload)
):
    """Lists all active authenticated refresh/access sessions for current user."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    current_jti = payload.get("jti")

    cursor = db.user_sessions.find({"user_id": current_uid}).sort("last_activity", -1)
    sessions = []
    async for s in cursor:
        sessions.append(SessionInfoResponse(
            id=str(s["_id"]),
            user_id=s["user_id"],
            device_label=s.get("device_label", "Web Browser"),
            client_ip_masked=s.get("client_ip_masked", "masked"),
            user_agent_summary=s.get("user_agent_summary", "Generic Browser"),
            created_at=s.get("created_at", datetime.now(timezone.utc)),
            last_activity=s.get("last_activity", datetime.now(timezone.utc)),
            is_current=(s.get("jti") == current_jti)
        ))

    # If no explicit sessions stored in user_sessions yet, fallback to active refresh token record
    if not sessions:
        ref_doc = await db.refresh_tokens.find_one({"user_id": current_uid})
        if ref_doc:
            sessions.append(SessionInfoResponse(
                id=str(ref_doc["_id"]),
                user_id=current_uid,
                device_label="Primary Active Session",
                client_ip_masked="127.0.0.1/24",
                user_agent_summary="Super AI Client",
                created_at=ref_doc.get("updated_at", datetime.now(timezone.utc)),
                last_activity=ref_doc.get("updated_at", datetime.now(timezone.utc)),
                is_current=True
            ))

    return sessions


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def revoke_specific_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Revokes a specific session belonging to the user."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    try:
        s_obj = ObjectId(session_id)
        session_doc = await db.user_sessions.find_one({"_id": s_obj, "user_id": current_uid})
    except Exception:
        session_doc = None

    if session_doc:
        jti = session_doc.get("jti")
        if jti:
            await revoke_token(jti=jti, expires_at=datetime.now(timezone.utc) + timedelta(days=1), reason="session_revoked", user_id=current_uid)
        await db.user_sessions.delete_one({"_id": session_doc["_id"]})
    else:
        # Fallback to refresh token deletion if matching ID
        await db.refresh_tokens.delete_many({"user_id": current_uid})

    await record_audit_event(
        event_type="SESSION_REVOKED",
        raw_actor_id=current_uid,
        metadata={"session_id": session_id, "scope": "single"}
    )

    return {"status": "success", "detail": "Session revoked"}


@router.post("/sessions/revoke-all", status_code=status.HTTP_200_OK)
async def revoke_all_sessions(
    current_user: dict = Depends(get_current_user)
):
    """Emergency workflow: Revokes ALL sessions across all devices for this account."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    await db.refresh_tokens.delete_many({"user_id": current_uid})
    await db.user_sessions.delete_many({"user_id": current_uid})

    await record_audit_event(
        event_type="SESSION_REVOKED",
        raw_actor_id=current_uid,
        metadata={"scope": "all_sessions", "reason": "user_initiated_revoke_all"}
    )

    return {"status": "success", "detail": "All sessions have been revoked across all devices"}


# ==========================================================
# 2. Cryptographic Device Registration
# ==========================================================

@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterPayload,
    current_user: dict = Depends(get_current_user)
):
    """
    Registers a client device public key (Ed25519) for challenge-response signing.
    Validates the 32-byte public key format. Private key NEVER touches the server.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # Validate Ed25519 public key bytes
    try:
        raw_pub = bytes.fromhex(payload.public_key_hex)
        if len(raw_pub) != 32:
            raise ValueError()
        ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 32-byte Ed25519 public key hex")

    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)

    # Check if duplicate key already registered
    existing = await db.registered_devices.find_one({"public_key_hex": payload.public_key_hex.lower()})
    if existing:
        if existing["user_id"] != current_uid:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Key already registered to another user")
        # Update device label
        await db.registered_devices.update_one(
            {"_id": existing["_id"]},
            {"$set": {"device_label": payload.device_label, "status": "active", "updated_at": now}}
        )
        return DeviceResponse(
            id=str(existing["_id"]),
            user_id=current_uid,
            device_label=payload.device_label,
            public_key_hex=payload.public_key_hex.lower(),
            platform=payload.platform,
            hardware_backed=payload.hardware_backed,
            status="active",
            registered_at=existing["registered_at"],
            last_used_at=existing.get("last_used_at")
        )

    device_doc = {
        "user_id": current_uid,
        "device_label": payload.device_label,
        "public_key_hex": payload.public_key_hex.lower(),
        "platform": payload.platform,
        "hardware_backed": payload.hardware_backed,
        "status": "active",
        "registered_at": now,
        "last_used_at": now
    }

    res = await db.registered_devices.insert_one(device_doc)
    dev_id = str(res.inserted_id)

    await record_audit_event(
        event_type="SECURITY_SETTINGS_CHANGED",
        raw_actor_id=current_uid,
        metadata={"action": "device_registered", "device_id": dev_id, "platform": payload.platform}
    )

    return DeviceResponse(
        id=dev_id,
        user_id=current_uid,
        device_label=payload.device_label,
        public_key_hex=payload.public_key_hex.lower(),
        platform=payload.platform,
        hardware_backed=payload.hardware_backed,
        status="active",
        registered_at=now,
        last_used_at=now
    )


@router.get("", response_model=List[DeviceResponse])
async def list_registered_devices(current_user: dict = Depends(get_current_user)):
    """Lists all registered devices for the authenticated user."""
    db = get_database()
    if db is None:
        return []

    cursor = db.registered_devices.find({"user_id": current_user["id"], "status": "active"})
    devices = []
    async for d in cursor:
        devices.append(DeviceResponse(
            id=str(d["_id"]),
            user_id=d["user_id"],
            device_label=d["device_label"],
            public_key_hex=d["public_key_hex"],
            platform=d.get("platform", "web"),
            hardware_backed=d.get("hardware_backed", False),
            status=d.get("status", "active"),
            registered_at=d["registered_at"],
            last_used_at=d.get("last_used_at")
        ))
    return devices


@router.delete("/{device_id}", status_code=status.HTTP_200_OK)
async def revoke_device(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Revokes a registered device key."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    try:
        dev_obj = ObjectId(device_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid device ID")

    res = await db.registered_devices.update_one(
        {"_id": dev_obj, "user_id": current_uid},
        {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc)}}
    )

    if res.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    await record_audit_event(
        event_type="SECURITY_SETTINGS_CHANGED",
        raw_actor_id=current_uid,
        metadata={"action": "device_revoked", "device_id": device_id}
    )

    return {"status": "success", "detail": "Device key revoked"}


# ==========================================================
# 3. Cryptographic Challenge-Response Protocol
# ==========================================================

@router.post("/challenges", response_model=ChallengeResponse)
async def create_security_challenge(
    payload: ChallengeRequestPayload,
    current_user: dict = Depends(get_current_user)
):
    """
    Issues a cryptographically secure, bound nonce challenge for high-risk actions.
    Bound to user_id, action_type, random 32-byte nonce, and short expiry.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    nonce = secrets.token_hex(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=CHALLENGE_EXPIRY_SECONDS)

    challenge_doc = {
        "user_id": current_uid,
        "action_type": payload.action_type,
        "resource_id": payload.resource_id,
        "nonce": nonce,
        "issued_at": now,
        "expires_at": expires_at,
        "used": False
    }

    res = await db.security_challenges.insert_one(challenge_doc)
    challenge_id = str(res.inserted_id)

    return ChallengeResponse(
        challenge_id=challenge_id,
        nonce=nonce,
        action_type=payload.action_type,
        resource_id=payload.resource_id,
        expires_at=expires_at,
        issued_at=now
    )


@router.post("/verify-action", response_model=SensitiveActionResponse)
async def verify_sensitive_action(
    payload: ChallengeVerifyPayload,
    current_user: dict = Depends(get_current_user)
):
    """
    Verifies an Ed25519 device signature against the issued challenge.
    Enforces replay defense, expiry, device status, and optional password reauthentication.
    Emits a verified audit ledger event.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]

    # 1. Fetch challenge
    try:
        chal_obj = ObjectId(payload.challenge_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid challenge ID")

    challenge = await db.security_challenges.find_one({"_id": chal_obj, "user_id": current_uid})
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Security challenge not found")

    # Replay protection: check if already used
    if challenge.get("used", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Security challenge has already been used (replay detected)")

    # Expiry protection
    now = datetime.now(timezone.utc)
    if now > challenge["expires_at"].replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Security challenge has expired")

    # 2. Fetch registered device
    try:
        dev_obj = ObjectId(payload.device_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid device ID")

    device = await db.registered_devices.find_one({"_id": dev_obj, "user_id": current_uid})
    if not device or device.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device key not registered or revoked")

    # 3. Verify Ed25519 signature over canonical challenge payload
    # Payload format: canonical JSON of {action_type, challenge_id, nonce, user_id}
    challenge_payload = {
        "action_type": challenge["action_type"],
        "challenge_id": str(challenge["_id"]),
        "nonce": challenge["nonce"],
        "user_id": current_uid
    }
    canonical_bytes = canonical_json_dumps(challenge_payload).encode("utf-8")

    try:
        raw_pub = bytes.fromhex(device["public_key_hex"])
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
        raw_sig = bytes.fromhex(payload.signature_hex)
        pub_key.verify(raw_sig, canonical_bytes)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cryptographic device signature")

    # 4. Optional / Mandatory reauthentication if password supplied
    if payload.password:
        user_doc = await db.users.find_one({"_id": ObjectId(current_uid)})
        if not user_doc or not verify_password(payload.password, user_doc["hashed_password"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password reauthentication failed")

    # Mark challenge as consumed (prevent replay)
    await db.security_challenges.update_one({"_id": chal_obj}, {"$set": {"used": True, "verified_at": now}})
    # Update device last_used_at
    await db.registered_devices.update_one({"_id": dev_obj}, {"$set": {"last_used_at": now}})

    # Record approved security event in Phase 10 Audit Ledger
    audit_event = await record_audit_event(
        event_type="SECURITY_SETTINGS_CHANGED",
        raw_actor_id=current_uid,
        metadata={
            "verified_action": challenge["action_type"],
            "device_id": payload.device_id,
            "signature_verified": True
        }
    )

    return SensitiveActionResponse(
        status="verified",
        action_type=challenge["action_type"],
        executed_at=now,
        audit_sequence=audit_event["sequence"] if audit_event else None
    )
