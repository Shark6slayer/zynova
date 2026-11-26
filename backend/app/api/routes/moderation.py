"""
ZENOVA — Phase 3 Safety, Reporting, Appeals & Moderator RBAC API Routes
Mounts:
- /api/v1/safety/*  (User-facing reporting, standing, appeals, policies)
- /api/v1/moderation/* (Role-protected moderator & admin dashboard)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.audit_ledger import record_audit_event
from app.core.rate_limit import check_report_rate_limit
from app.database.client import get_database
from app.services.moderation_service import (
    HIGH_PRIORITY_CATEGORIES,
    REPORT_CATEGORIES,
    REPORT_STATUSES,
    REPORT_TARGET_TYPES,
    VALID_REPORT_TRANSITIONS,
    apply_account_enforcement,
    record_moderation_decision,
)
import html
from app.services.notification_service import create_event_notification


def sanitize_text(text: str) -> str:
    return html.escape(text.strip())

safety_router = APIRouter(prefix="/safety", tags=["User Safety & Appeals"])
mod_router = APIRouter(prefix="/moderation", tags=["Moderator & Admin Operations"])


# --------------------------------------------------------------------------
# RBAC Dependencies (Backend-Enforced, Least-Privilege)
# --------------------------------------------------------------------------
def _get_role(user: dict) -> str:
    return (user.get("role") or "regular").lower().strip()


async def require_moderator(current_user: dict = Depends(get_current_user)) -> dict:
    if _get_role(current_user) not in {"moderator", "senior_moderator", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator authorization required.",
        )
    return current_user


async def require_senior_moderator(current_user: dict = Depends(get_current_user)) -> dict:
    if _get_role(current_user) not in {"senior_moderator", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Senior moderator or administrator authorization required.",
        )
    return current_user


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
class SafetyReportCreate(BaseModel):
    target_type: str
    target_id: str = Field(..., min_length=1, max_length=128)
    category: str
    description: Optional[str] = Field(None, max_length=1000)
    evidence_urls: Optional[List[str]] = Field(default=None, max_length=5)


class ReportTransitionRequest(BaseModel):
    new_status: str
    note: Optional[str] = Field(None, max_length=500)


class ModeratorActionRequest(BaseModel):
    action: str  # dismiss, remove_content, restrict_content, restore_content, warn_user, restrict_account, suspend_account, escalate, resolve
    reason: str = Field(..., min_length=3, max_length=500)
    enforcement_tier: Optional[str] = None
    duration_hours: Optional[int] = Field(default=24, ge=1, le=8760)
    note: Optional[str] = Field(None, max_length=500)


class AppealCreateRequest(BaseModel):
    target_type: str = Field(..., pattern="^(content|enforcement)$")
    target_id: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=10, max_length=1000)


class AppealReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject|escalate)$")
    reasoning: str = Field(..., min_length=5, max_length=500)


# --------------------------------------------------------------------------
# Phase 3.1: User Reporting Infrastructure
# --------------------------------------------------------------------------
@safety_router.post("/reports", status_code=status.HTTP_201_CREATED)
async def submit_safety_report(
    body: SafetyReportCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    target_type = body.target_type.strip().lower()
    category = body.category.strip().lower()
    if target_type not in REPORT_TARGET_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported target_type: {target_type}")
    if category not in REPORT_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid report category: {category}")

    my_id = current_user["id"]
    check_report_rate_limit(my_id)

    existing = await db.reports.find_one({
        "reporter_id": my_id,
        "target_type": target_type,
        "target_id": body.target_id,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already submitted a report for this content.",
        )

    now = datetime.now(timezone.utc)
    priority = "high" if category in HIGH_PRIORITY_CATEGORIES else "normal"
    initial_status = "ESCALATED" if category == "child_safety" else "PENDING"

    report_doc = {
        "reporter_id": my_id,
        "target_type": target_type,
        "target_id": body.target_id,
        "category": category,
        "reason": category,
        "description": sanitize_text(body.description) if body.description else None,
        "evidence_urls": body.evidence_urls or [],
        "priority": priority,
        "status": initial_status,
        "moderator_notes": [],
        "assigned_moderator_id": None,
        "created_at": now,
        "updated_at": now,
    }
    res = await db.reports.insert_one(report_doc)
    report_id = str(res.inserted_id)

    await record_audit_event(
        event_type="SAFETY_REPORT_SUBMITTED",
        raw_actor_id=my_id,
        metadata={"report_id": report_id, "target_type": target_type, "category": category, "priority": priority},
    )

    await create_event_notification(
        recipient_user_id=my_id,
        actor_user_id=None,
        category="safety",
        event_type="report_received",
        title="Safety Report Received",
        desc=f"Your {category.replace('_', ' ')} report has been queued for review.",
        navigation_target=f"safety:report:{report_id}",
        metadata={"report_id": report_id},
        event_id=f"rep_rx_{report_id}",
    )

    return {
        "id": report_id,
        "target_type": target_type,
        "target_id": body.target_id,
        "category": category,
        "priority": priority,
        "status": initial_status,
        "created_at": now.isoformat(),
    }


@safety_router.get("/reports/me")
async def list_my_reports(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        return []
    cursor = db.reports.find({"reporter_id": current_user["id"]}).sort("created_at", -1).limit(limit)
    out = []
    async for r in cursor:
        out.append({
            "id": str(r["_id"]),
            "target_type": r["target_type"],
            "target_id": r["target_id"],
            "category": r.get("category") or r.get("reason"),
            "priority": r.get("priority", "normal"),
            "status": r.get("status", "PENDING").upper(),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
        })
    return out


# --------------------------------------------------------------------------
# Phase 3.7: Appeals & User Transparency
# --------------------------------------------------------------------------
@safety_router.get("/policies")
async def get_safety_policies():
    return {
        "categories": sorted(REPORT_CATEGORIES),
        "target_types": sorted(REPORT_TARGET_TYPES),
        "enforcement_tiers": ["warning", "content_restriction", "temporary_interaction_restriction", "temporary_suspension", "permanent_suspension"],
        "appeal_policy": "Users may appeal content restrictions or account enforcements within 30 days. Human moderators review all appeals.",
    }


@safety_router.get("/account-standing")
async def get_my_account_standing(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return {"standing": "good", "enforcements": []}
    cursor = db.account_enforcements.find({"user_id": current_user["id"]}).sort("created_at", -1).limit(10)
    enforcements = []
    async for e in cursor:
        enforcements.append({
            "id": str(e["_id"]),
            "tier": e["tier"],
            "reason": e["reason"],
            "active": e.get("active", True),
            "created_at": e["created_at"].isoformat() if e.get("created_at") else "",
            "expires_at": e["expires_at"].isoformat() if e.get("expires_at") else None,
        })
    return {
        "standing": current_user.get("safety_standing", "good"),
        "content_restricted_until": current_user.get("content_restricted_until"),
        "interaction_restricted_until": current_user.get("interaction_restricted_until"),
        "enforcements": enforcements,
    }


@safety_router.post("/appeals", status_code=status.HTTP_201_CREATED)
async def submit_appeal(
    body: AppealCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    my_id = current_user["id"]
    existing = await db.safety_appeals.find_one({
        "user_id": my_id,
        "target_type": body.target_type,
        "target_id": body.target_id,
        "status": "PENDING",
    })
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An appeal for this decision is already pending review.")

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": my_id,
        "target_type": body.target_type,
        "target_id": body.target_id,
        "reason": sanitize_text(body.reason),
        "status": "PENDING",
        "reviewer_id": None,
        "reviewer_reasoning": None,
        "created_at": now,
        "updated_at": now,
    }
    res = await db.safety_appeals.insert_one(doc)
    appeal_id = str(res.inserted_id)

    await record_audit_event(
        event_type="SAFETY_APPEAL_SUBMITTED",
        raw_actor_id=my_id,
        metadata={"appeal_id": appeal_id, "target_type": body.target_type, "target_id": body.target_id},
    )
    return {
        "id": appeal_id,
        "target_type": body.target_type,
        "target_id": body.target_id,
        "status": "PENDING",
        "created_at": now.isoformat(),
    }


@safety_router.get("/appeals/me")
async def list_my_appeals(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return []
    cursor = db.safety_appeals.find({"user_id": current_user["id"]}).sort("created_at", -1).limit(20)
    out = []
    async for a in cursor:
        out.append({
            "id": str(a["_id"]),
            "target_type": a["target_type"],
            "target_id": a["target_id"],
            "reason": a["reason"],
            "status": a["status"],
            "reviewer_reasoning": a.get("reviewer_reasoning"),
            "created_at": a["created_at"].isoformat() if a.get("created_at") else "",
        })
    return out


# --------------------------------------------------------------------------
# Phase 3.6: Moderator & Admin Dashboard (RBAC Protected)
# --------------------------------------------------------------------------
@mod_router.get("/queue")
async def get_moderation_queue(
    status_filter: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    mod_user: dict = Depends(require_moderator),
):
    db = get_database()
    if db is None:
        return []
    query: Dict[str, Any] = {}
    if status_filter:
        query["status"] = {"$in": [status_filter.upper(), status_filter.lower()]}
    if priority:
        query["priority"] = priority.lower()

    cursor = db.reports.find(query).sort([("priority", 1), ("created_at", -1)]).limit(limit)
    items = []
    async for r in cursor:
        items.append({
            "id": str(r["_id"]),
            "target_type": r["target_type"],
            "target_id": r["target_id"],
            "category": r.get("category") or r.get("reason"),
            "priority": r.get("priority", "normal"),
            "status": str(r.get("status", "PENDING")).upper(),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
        })
    return items


@mod_router.get("/reports/{report_id}")
async def get_moderation_report_detail(
    report_id: str,
    mod_user: dict = Depends(require_moderator),
):
    db = get_database()
    if db is None or not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    r = await db.reports.find_one({"_id": ObjectId(report_id)})
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # Fetch associated non-private content preview when post/comment
    associated_content = None
    if r["target_type"] == "post" and ObjectId.is_valid(r["target_id"]):
        p = await db.posts.find_one({"_id": ObjectId(r["target_id"])}, {"content": 1, "author_id": 1, "moderation_status": 1})
        if p:
            associated_content = {"content": p.get("content"), "author_id": p.get("author_id"), "moderation_status": p.get("moderation_status", "active")}

    return {
        "id": str(r["_id"]),
        "target_type": r["target_type"],
        "target_id": r["target_id"],
        "category": r.get("category") or r.get("reason"),
        "description": r.get("description"),
        "priority": r.get("priority", "normal"),
        "status": str(r.get("status", "PENDING")).upper(),
        "moderator_notes": r.get("moderator_notes", []),
        "associated_content": associated_content,
        "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
    }


@mod_router.post("/reports/{report_id}/transition")
async def transition_report_status(
    report_id: str,
    body: ReportTransitionRequest,
    mod_user: dict = Depends(require_moderator),
):
    db = get_database()
    if db is None or not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    r = await db.reports.find_one({"_id": ObjectId(report_id)})
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    current_status = str(r.get("status", "PENDING")).upper()
    target_status = body.new_status.strip().upper()
    if target_status not in REPORT_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid report status")
    if target_status not in VALID_REPORT_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition from {current_status} to {target_status}",
        )

    now = datetime.now(timezone.utc)
    update_ops: Dict[str, Any] = {
        "$set": {"status": target_status, "assigned_moderator_id": mod_user["id"], "updated_at": now}
    }
    if body.note:
        update_ops["$push"] = {
            "moderator_notes": {"moderator_id": mod_user["id"], "note": sanitize_text(body.note), "at": now.isoformat()}
        }
    await db.reports.update_one({"_id": ObjectId(report_id)}, update_ops)

    await record_audit_event(
        event_type="MODERATION_REPORT_TRANSITION",
        raw_actor_id=mod_user["id"],
        metadata={"report_id": report_id, "from": current_status, "to": target_status},
    )
    return {"id": report_id, "previous_status": current_status, "status": target_status}


@mod_router.post("/reports/{report_id}/action")
async def execute_moderator_action(
    report_id: str,
    body: ModeratorActionRequest,
    mod_user: dict = Depends(require_moderator),
):
    db = get_database()
    if db is None or not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    r = await db.reports.find_one({"_id": ObjectId(report_id)})
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    act = body.action.strip().lower()
    mod_role = _get_role(mod_user)
    now = datetime.now(timezone.utc)
    new_status = "RESOLVED"
    subject_user_id = None

    if r["target_type"] == "post" and ObjectId.is_valid(r["target_id"]):
        post = await db.posts.find_one({"_id": ObjectId(r["target_id"])})
        if post:
            subject_user_id = post.get("author_id")
            if act in {"remove_content", "restrict_content"}:
                mod_state = "removed" if act == "remove_content" else "restricted"
                await db.posts.update_one({"_id": post["_id"]}, {"$set": {"moderation_status": mod_state, "updated_at": now}})
                if subject_user_id:
                    await create_event_notification(
                        recipient_user_id=subject_user_id,
                        actor_user_id=None,
                        category="safety",
                        event_type="content_removed" if mod_state == "removed" else "content_restricted",
                        title="Content Policy Action",
                        desc=f"Your post was {mod_state}: {body.reason}",
                        navigation_target=f"safety:appeal:{r['target_id']}",
                        event_id=f"mod_{report_id}_{mod_state}",
                    )
            elif act == "restore_content":
                await db.posts.update_one({"_id": post["_id"]}, {"$set": {"moderation_status": "active", "updated_at": now}})
                if subject_user_id:
                    await create_event_notification(
                        recipient_user_id=subject_user_id,
                        actor_user_id=None,
                        category="safety",
                        event_type="content_restored",
                        title="Content Restored",
                        desc="Your post has been reviewed and restored.",
                        navigation_target=f"social:post:{r['target_id']}",
                        event_id=f"mod_{report_id}_restored",
                    )
    elif r["target_type"] in {"user", "profile"}:
        subject_user_id = r["target_id"]

    if act == "dismiss":
        new_status = "REJECTED"
    elif act == "escalate":
        new_status = "ESCALATED"
    elif act in {"warn_user", "restrict_account", "suspend_account"}:
        if not subject_user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to resolve subject user for enforcement")
        tier = body.enforcement_tier or (
            "warning" if act == "warn_user" else "temporary_interaction_restriction" if act == "restrict_account" else "temporary_suspension"
        )
        try:
            await apply_account_enforcement(
                db=db,
                target_user_id=subject_user_id,
                tier=tier,
                reason=body.reason,
                moderator_id=mod_user["id"],
                moderator_role=mod_role,
                duration_hours=body.duration_hours,
                report_id=report_id,
            )
        except PermissionError as pe:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))

    await db.reports.update_one(
        {"_id": ObjectId(report_id)},
        {
            "$set": {"status": new_status, "assigned_moderator_id": mod_user["id"], "updated_at": now},
            "$push": {"moderator_notes": {"moderator_id": mod_user["id"], "action": act, "note": sanitize_text(body.note or body.reason), "at": now.isoformat()}},
        },
    )

    await record_moderation_decision(
        db=db,
        target_type=r["target_type"],
        target_id=r["target_id"],
        actor_id=subject_user_id or "unknown",
        evaluation={"decision": act.upper(), "severity_score": 1.0 if act == "suspend_account" else 0.5, "categories": [r.get("category", "other")]},
        moderator_id=mod_user["id"],
        reason=body.reason,
    )

    # Notify reporter of resolution (without exposing private user/evidence internals)
    if new_status in {"RESOLVED", "REJECTED"} and r.get("reporter_id"):
        await create_event_notification(
            recipient_user_id=r["reporter_id"],
            actor_user_id=None,
            category="safety",
            event_type="report_resolved",
            title="Safety Report Update",
            desc=f"Your report has been reviewed (status: {new_status}).",
            navigation_target=f"safety:report:{report_id}",
            event_id=f"rep_res_{report_id}_{new_status}",
        )

    return {"report_id": report_id, "action": act, "status": new_status}


@mod_router.get("/appeals")
async def list_moderation_appeals(
    status_filter: str = Query("PENDING"),
    mod_user: dict = Depends(require_moderator),
):
    db = get_database()
    if db is None:
        return []
    cursor = db.safety_appeals.find({"status": status_filter.upper()}).sort("created_at", 1).limit(50)
    out = []
    async for a in cursor:
        out.append({
            "id": str(a["_id"]),
            "user_id": a["user_id"],
            "target_type": a["target_type"],
            "target_id": a["target_id"],
            "reason": a["reason"],
            "status": a["status"],
            "created_at": a["created_at"].isoformat() if a.get("created_at") else "",
        })
    return out


@mod_router.post("/appeals/{appeal_id}/review")
async def review_appeal(
    appeal_id: str,
    body: AppealReviewRequest,
    mod_user: dict = Depends(require_moderator),
):
    db = get_database()
    if db is None or not ObjectId.is_valid(appeal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appeal not found")
    appeal = await db.safety_appeals.find_one({"_id": ObjectId(appeal_id)})
    if not appeal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appeal not found")

    now = datetime.now(timezone.utc)
    dec = body.decision.lower()
    new_status = "APPROVED" if dec == "approve" else "ESCALATED" if dec == "escalate" else "REJECTED"

    if dec == "approve":
        if appeal["target_type"] == "content" and ObjectId.is_valid(appeal["target_id"]):
            await db.posts.update_one({"_id": ObjectId(appeal["target_id"])}, {"$set": {"moderation_status": "active", "updated_at": now}})
        elif appeal["target_type"] == "enforcement":
            await db.users.update_one(
                {"_id": ObjectId(appeal["user_id"])},
                {"$set": {
                    "safety_standing": "good",
                    "is_active": True,
                    "account_status": "active",
                    "content_restricted_until": None,
                    "interaction_restricted_until": None,
                    "updated_at": now,
                }},
            )
            if ObjectId.is_valid(appeal["target_id"]):
                await db.account_enforcements.update_one({"_id": ObjectId(appeal["target_id"])}, {"$set": {"active": False, "reversed_at": now}})

    await db.safety_appeals.update_one(
        {"_id": ObjectId(appeal_id)},
        {"$set": {"status": new_status, "reviewer_id": mod_user["id"], "reviewer_reasoning": sanitize_text(body.reasoning), "updated_at": now}},
    )

    await record_audit_event(
        event_type="MODERATION_APPEAL_REVIEWED",
        raw_actor_id=mod_user["id"],
        metadata={"appeal_id": appeal_id, "decision": new_status},
    )

    await create_event_notification(
        recipient_user_id=appeal["user_id"],
        actor_user_id=None,
        category="safety",
        event_type="appeal_decision",
        title="Appeal Decision",
        desc=f"Your appeal was {new_status.lower()}: {body.reasoning}",
        navigation_target=f"safety:appeal:{appeal_id}",
        event_id=f"app_dec_{appeal_id}_{new_status}",
    )
    return {"appeal_id": appeal_id, "status": new_status}


@mod_router.get("/audit-logs")
async def list_moderation_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    mod_user: dict = Depends(require_senior_moderator),
):
    db = get_database()
    if db is None:
        return []
    cursor = db.audit_ledger.find(
        {"event_type": {"$regex": "^(MODERATION_|ENFORCEMENT_|SAFETY_)"}}
    ).sort("sequence", -1).limit(limit)
    out = []
    async for doc in cursor:
        out.append({
            "sequence": doc.get("sequence"),
            "event_type": doc.get("event_type"),
            "timestamp": doc.get("timestamp"),
            "metadata": doc.get("metadata", {}),
        })
    return out
