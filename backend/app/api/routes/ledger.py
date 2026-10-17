"""
routes/ledger.py - Audit Ledger Administrative & Verification Endpoints (Phase 10)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.audit_ledger import (
    verify_ledger_records,
    create_ledger_checkpoint,
    get_signer_public_key_hex,
    record_audit_event
)

router = APIRouter(prefix="/ledger", tags=["Audit Ledger"])

@router.get("/status")
async def get_ledger_status(current_user: dict = Depends(get_current_user)):
    """Returns ledger operational status and verification summary."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    count = await db.audit_ledger.count_documents({})
    latest_event = await db.audit_ledger.find_one(sort=[("sequence", -1)])
    checkpoint_count = await db.ledger_checkpoints.count_documents({})
    latest_cp = await db.ledger_checkpoints.find_one(sort=[("end_sequence", -1)])

    return {
        "status": "operational",
        "events_count": count,
        "latest_sequence": latest_event["sequence"] if latest_event else 0,
        "latest_hash": latest_event["current_hash"] if latest_event else None,
        "checkpoints_count": checkpoint_count,
        "latest_checkpoint_sequence": latest_cp["end_sequence"] if latest_cp else None,
        "signer_public_key": get_signer_public_key_hex()
    }

@router.get("/verify")
async def verify_ledger(current_user: dict = Depends(get_current_user)):
    """Runs independent verification over the entire ledger chain stored in MongoDB."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    cursor = db.audit_ledger.find({}).sort("sequence", 1)
    records = []
    async for rec in cursor:
        rec_clean = {
            "schema_version": rec.get("schema_version"),
            "sequence": rec.get("sequence"),
            "timestamp": rec.get("timestamp"),
            "event_type": rec.get("event_type"),
            "actor_pseudonym": rec.get("actor_pseudonym"),
            "metadata": rec.get("metadata", {}),
            "prev_hash": rec.get("prev_hash"),
            "current_hash": rec.get("current_hash"),
        }
        records.append(rec_clean)

    res = verify_ledger_records(records)
    
    # Audit this verification check
    await record_audit_event(
        event_type="CHECKPOINT_VERIFIED",
        raw_actor_id=current_user["id"],
        metadata={"verified_count": len(records), "is_valid": res["valid"]}
    )

    return res

@router.get("/export")
async def export_ledger(
    limit: int = Query(500, ge=1, le=5000),
    current_user: dict = Depends(get_current_user)
):
    """Exports records and signed checkpoints for third-party independent audit."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    records = []
    cursor = db.audit_ledger.find({}).sort("sequence", 1).limit(limit)
    async for rec in cursor:
        records.append({
            "schema_version": rec.get("schema_version"),
            "sequence": rec.get("sequence"),
            "timestamp": rec.get("timestamp"),
            "event_type": rec.get("event_type"),
            "actor_pseudonym": rec.get("actor_pseudonym"),
            "metadata": rec.get("metadata", {}),
            "prev_hash": rec.get("prev_hash"),
            "current_hash": rec.get("current_hash"),
        })

    checkpoints = []
    cp_cursor = db.ledger_checkpoints.find({}).sort("end_sequence", 1)
    async for cp in cp_cursor:
        checkpoints.append({
            "checkpoint_version": cp.get("checkpoint_version"),
            "end_hash": cp.get("end_hash"),
            "end_sequence": cp.get("end_sequence"),
            "public_key": cp.get("public_key"),
            "timestamp": cp.get("timestamp"),
            "signature": cp.get("signature")
        })

    anchors = []
    anc_cursor = db.blockchain_anchors.find({}).sort("sequence", 1)
    async for anc in anc_cursor:
        anchors.append({
            "sequence": anc.get("sequence"),
            "checkpoint_hash": anc.get("checkpoint_hash"),
            "schema_version": anc.get("schema_version"),
            "network": anc.get("network"),
            "chain_id": anc.get("chain_id"),
            "contract_address": anc.get("contract_address"),
            "submitter": anc.get("submitter"),
            "status": anc.get("status"),
            "tx_hash": anc.get("tx_hash"),
            "block_number": anc.get("block_number"),
            "created_at": anc.get("created_at")
        })

    return {
        "records": records,
        "checkpoints": checkpoints,
        "blockchain_anchors": anchors,
        "exported_at_utc": str(records[-1]["timestamp"] if records else None)
    }

@router.post("/checkpoints", status_code=status.HTTP_201_CREATED)
async def trigger_checkpoint(current_user: dict = Depends(get_current_user)):
    """Manually creates a signed checkpoint at the current ledger head."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    latest_event = await db.audit_ledger.find_one(sort=[("sequence", -1)])
    if not latest_event:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ledger is empty; cannot checkpoint.")

    cp = await create_ledger_checkpoint(latest_event["sequence"], latest_event["current_hash"])
    await record_audit_event(
        event_type="CHECKPOINT_CREATED",
        raw_actor_id=current_user["id"],
        metadata={"end_sequence": cp["end_sequence"], "end_hash": cp["end_hash"][:16]}
    )
    return cp

@router.post("/anchors", status_code=status.HTTP_201_CREATED)
async def trigger_blockchain_anchor(
    sequence: Optional[int] = Query(None, description="Sequence to anchor; defaults to latest checkpoint"),
    current_user: dict = Depends(get_current_user)
):
    """Submits a verified checkpoint commitment to the blockchain anchor subsystem."""
    from app.core.blockchain_anchor import submit_checkpoint_anchor
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    query = {"end_sequence": sequence} if sequence else {}
    cp = await db.ledger_checkpoints.find_one(query, sort=[("end_sequence", -1)])
    if not cp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkpoint not found for anchoring")

    res = await submit_checkpoint_anchor(cp)
    return res
