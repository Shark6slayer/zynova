"""
ZENOVA — Phase 3 Centralized Social Safety, Content Moderation & Enforcement Engine
Provides:
- Input normalization, multi-signal text/link policy scoring, and quarantine decisions
- Asynchronous media/video/reels moderation queue (with explicit external provider boundary)
- Validated Report Lifecycle state machine (PENDING -> UNDER_REVIEW -> ACTION_REQUIRED -> RESOLVED/REJECTED/ESCALATED)
- 5-Tier Controlled Account Enforcement Framework (Warning -> Human-Reviewed Suspension)
- Spam, duplicate content, and suspicious URL detection
- Safety notification dispatch & immutable audit trail logging
"""

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId

from app.core.audit_ledger import record_audit_event
from app.services.notification_service import create_event_notification

logger = logging.getLogger("super_ai.moderation")

REPORT_CATEGORIES = {
    "spam",
    "harassment",
    "bullying",
    "hate_speech",
    "violence",
    "threats",
    "sexual_content",
    "child_safety",
    "impersonation",
    "fraud_scams",
    "misinformation",
    "ip_violation",
    "other",
}

REPORT_TARGET_TYPES = {
    "user",
    "profile",
    "post",
    "comment",
    "reel",
    "message",
    "group",
}

REPORT_STATUSES = {
    "PENDING",
    "UNDER_REVIEW",
    "ACTION_REQUIRED",
    "RESOLVED",
    "REJECTED",
    "ESCALATED",
}

VALID_REPORT_TRANSITIONS: Dict[str, set] = {
    "PENDING": {"UNDER_REVIEW", "ACTION_REQUIRED", "RESOLVED", "REJECTED", "ESCALATED"},
    "UNDER_REVIEW": {"ACTION_REQUIRED", "RESOLVED", "REJECTED", "ESCALATED"},
    "ACTION_REQUIRED": {"UNDER_REVIEW", "RESOLVED", "REJECTED", "ESCALATED"},
    "ESCALATED": {"UNDER_REVIEW", "ACTION_REQUIRED", "RESOLVED", "REJECTED"},
    "RESOLVED": {"UNDER_REVIEW"},  # Reopenable on appeal
    "REJECTED": {"UNDER_REVIEW"},  # Reopenable on appeal
}

HIGH_PRIORITY_CATEGORIES = {"child_safety", "threats", "violence", "sexual_content", "fraud_scams"}

ENFORCEMENT_TIERS = {
    "warning": 1,
    "content_restriction": 2,
    "temporary_interaction_restriction": 3,
    "temporary_suspension": 4,
    "permanent_suspension": 5,
}

# Multi-signal heuristic lexicons (normalized lowercase)
_CRITICAL_PATTERNS = [
    r"\bcsam\b",
    r"\bchild\s+exploit",
    r"\bkill\s+you\b",
    r"\bi\s+will\s+murder\b",
    r"\bbomb\s+threat\b",
    r"\bshoot\s+up\b",
]
_HARASSMENT_PATTERNS = [
    r"\bkill\s+yourself\b",
    r"\bkys\b",
    r"\bworthless\s+trash\b",
    r"\bharass",
    r"\bstalk\s+you\b",
    r"\bdoxx",
]
_SCAM_PATTERNS = [
    r"\bsend\s+otp\b",
    r"\bshare\s+your\s+pin\b",
    r"\bfree\s+crypto\s+giveaway\b",
    r"\bdouble\s+your\s+upi\b",
    r"\bguaranteed\s+100x\s+return\b",
]
_SUSPICIOUS_URL_RE = re.compile(
    r"(https?://(?:\d{1,3}\.){3}\d{1,3}[^\s]*|https?://[^\s]+\.(?:tk|ml|ga|cf|gq|xyz|top)/[^\s]*)",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def normalize_moderation_text(text: str) -> str:
    """Normalizes unicode, strips zero-width characters, and collapses whitespace."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", text)
    norm = re.sub(r"[\u200B-\u200D\uFEFF]", "", norm)
    norm = re.sub(r"\s+", " ", norm).strip().lower()
    return norm


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(normalize_moderation_text(text).encode("utf-8")).hexdigest()


def evaluate_text_content(text: str, context: str = "post") -> Dict[str, Any]:
    """
    Evaluates text for safety policy violations using normalized multi-signal scoring.
    Never issues automatic permanent account bans solely from an automated score.
    """
    norm = normalize_moderation_text(text)
    if not norm:
        return {
            "decision": "ALLOW",
            "severity_score": 0.0,
            "categories": [],
            "requires_human_review": False,
            "suspicious_urls": [],
            "context": context,
        }

    score = 0.0
    categories: List[str] = []

    for pat in _CRITICAL_PATTERNS:
        if re.search(pat, norm):
            score = max(score, 0.92)
            categories.append("threats" if "kill" in pat or "bomb" in pat or "shoot" in pat or "murder" in pat else "child_safety")

    for pat in _HARASSMENT_PATTERNS:
        if re.search(pat, norm):
            score = max(score, 0.72)
            if "harassment" not in categories:
                categories.append("harassment")

    for pat in _SCAM_PATTERNS:
        if re.search(pat, norm):
            score = max(score, 0.68)
            if "fraud_scams" not in categories:
                categories.append("fraud_scams")

    suspicious_urls = _SUSPICIOUS_URL_RE.findall(text)
    if suspicious_urls:
        score = max(score, 0.75)
        if "fraud_scams" not in categories:
            categories.append("fraud_scams")

    # Excessive link spam heuristic
    all_urls = _URL_RE.findall(text)
    if len(all_urls) >= 4:
        score = max(score, 0.55)
        if "spam" not in categories:
            categories.append("spam")

    if score >= 0.85:
        decision = "ESCALATE"  # Quarantine/restrict pending human moderator review
    elif score >= 0.65:
        decision = "RESTRICT"
    elif score >= 0.45:
        decision = "FLAG"
    else:
        decision = "ALLOW"

    return {
        "decision": decision,
        "severity_score": round(score, 3),
        "categories": sorted(set(categories)),
        "requires_human_review": decision in {"ESCALATE", "RESTRICT"},
        "suspicious_urls": suspicious_urls,
        "context": context,
    }


async def check_duplicate_spam_burst(db, user_id: str, content_hash: str, window_minutes: int = 10, threshold: int = 3) -> bool:
    """Detects repeated identical posts/messages within a short window."""
    if db is None or not content_hash:
        return False
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    count = await db.moderation_content_hashes.count_documents({
        "user_id": user_id,
        "content_hash": content_hash,
        "created_at": {"$gte": since},
    })
    await db.moderation_content_hashes.insert_one({
        "user_id": user_id,
        "content_hash": content_hash,
        "created_at": datetime.now(timezone.utc),
    })
    return count >= threshold


async def record_moderation_decision(
    db,
    target_type: str,
    target_id: str,
    actor_id: str,
    evaluation: Dict[str, Any],
    moderator_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[str]:
    if db is None:
        return None
    now = datetime.now(timezone.utc)
    doc = {
        "target_type": target_type,
        "target_id": target_id,
        "subject_user_id": actor_id,
        "moderator_id": moderator_id,
        "decision": evaluation["decision"],
        "severity_score": evaluation.get("severity_score", 0.0),
        "categories": evaluation.get("categories", []),
        "requires_human_review": evaluation.get("requires_human_review", False),
        "reason": reason,
        "created_at": now,
    }
    res = await db.moderation_decisions.insert_one(doc)
    await record_audit_event(
        event_type=f"MODERATION_{evaluation['decision']}",
        raw_actor_id=moderator_id or "system_moderation_engine",
        metadata={
            "target_type": target_type,
            "target_id": target_id,
            "decision": evaluation["decision"],
            "severity": evaluation.get("severity_score", 0.0),
        },
    )
    return str(res.inserted_id)


async def enqueue_media_moderation(
    db,
    target_type: str,
    target_id: str,
    owner_id: str,
    media_type: str,
    filename: Optional[str] = None,
    caption: Optional[str] = None,
) -> Optional[str]:
    """
    Queues image/video/reel media for asynchronous moderation review.
    Explicitly marks external AI vision/video scanning as an integration boundary
    when no external classifier is configured.
    """
    if db is None:
        return None
    text_eval = evaluate_text_content(caption or "", context=f"{target_type}_caption")
    now = datetime.now(timezone.utc)
    job = {
        "target_type": target_type,
        "target_id": target_id,
        "owner_id": owner_id,
        "media_type": media_type,
        "filename": filename,
        "caption_decision": text_eval["decision"],
        "status": "escalated_for_human_review" if text_eval["requires_human_review"] else "queued_for_async_scan",
        "external_classifier_status": "requires_external_integration",
        "created_at": now,
        "updated_at": now,
    }
    res = await db.moderation_media_jobs.insert_one(job)
    return str(res.inserted_id)


async def apply_account_enforcement(
    db,
    target_user_id: str,
    tier: str,
    reason: str,
    moderator_id: str,
    moderator_role: str,
    duration_hours: Optional[int] = None,
    report_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Applies a controlled 5-tier account enforcement action.
    Permanent suspension requires senior_moderator or admin role.
    """
    if tier not in ENFORCEMENT_TIERS:
        raise ValueError(f"Invalid enforcement tier: {tier}")
    if tier == "permanent_suspension" and moderator_role not in {"senior_moderator", "admin"}:
        raise PermissionError("Permanent suspension requires senior_moderator or admin authorization.")
    if not ObjectId.is_valid(target_user_id):
        raise ValueError("Invalid target user ID")

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=duration_hours)) if duration_hours and tier != "permanent_suspension" else None

    enforcement_doc = {
        "user_id": target_user_id,
        "tier": tier,
        "tier_level": ENFORCEMENT_TIERS[tier],
        "reason": reason,
        "moderator_id": moderator_id,
        "report_id": report_id,
        "active": True,
        "created_at": now,
        "expires_at": expires_at,
    }
    res = await db.account_enforcements.insert_one(enforcement_doc)
    enforcement_id = str(res.inserted_id)

    user_updates: Dict[str, Any] = {
        "safety_standing": tier,
        "last_enforcement_id": enforcement_id,
        "updated_at": now,
    }
    if tier == "content_restriction":
        user_updates["content_restricted_until"] = expires_at or (now + timedelta(hours=24))
    elif tier == "temporary_interaction_restriction":
        user_updates["interaction_restricted_until"] = expires_at or (now + timedelta(hours=48))
    elif tier in {"temporary_suspension", "permanent_suspension"}:
        user_updates["is_active"] = False
        user_updates["account_status"] = tier
        user_updates["suspension_expires_at"] = expires_at

    await db.users.update_one({"_id": ObjectId(target_user_id)}, {"$set": user_updates})

    await record_audit_event(
        event_type=f"ENFORCEMENT_{tier.upper()}",
        raw_actor_id=moderator_id,
        metadata={"target_user_id": target_user_id, "tier": tier, "enforcement_id": enforcement_id, "report_id": report_id},
    )

    notif_titles = {
        "warning": "Account Safety Warning",
        "content_restriction": "Content Posting Temporarily Restricted",
        "temporary_interaction_restriction": "Interactions Temporarily Restricted",
        "temporary_suspension": "Account Temporarily Suspended",
        "permanent_suspension": "Account Suspended",
    }
    await create_event_notification(
        recipient_user_id=target_user_id,
        actor_user_id=None,
        category="safety",
        event_type=f"safety_{tier}",
        title=notif_titles[tier],
        desc=f"Action reason: {reason}. You may submit an appeal in Safety & Appeals.",
        navigation_target=f"safety:appeal:{enforcement_id}",
        metadata={"enforcement_id": enforcement_id, "tier": tier},
        event_id=f"enf_{enforcement_id}",
    )

    return {
        "enforcement_id": enforcement_id,
        "user_id": target_user_id,
        "tier": tier,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "created_at": now.isoformat(),
    }


async def check_user_safety_restriction(db, user_id: str, action: str) -> Optional[str]:
    """
    Returns an error reason string if user currently has an active content/interaction restriction,
    automatically clearing expired temporary restrictions.
    """
    if db is None or not ObjectId.is_valid(user_id):
        return None
    user = await db.users.find_one(
        {"_id": ObjectId(user_id)},
        {"content_restricted_until": 1, "interaction_restricted_until": 1, "safety_standing": 1},
    )
    if not user:
        return None
    now = datetime.now(timezone.utc)

    if action in {"post", "reel"}:
        until = user.get("content_restricted_until")
        if until:
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until > now:
                return "Your account is currently under a temporary content restriction."

    if action in {"comment", "message", "like"}:
        until = user.get("interaction_restricted_until")
        if until:
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until > now:
                return "Your account is currently under a temporary interaction restriction."

    return None
