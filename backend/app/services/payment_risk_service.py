"""
ZENOVA Pay — Phase 4.3 & 4.5 Transaction State Machine & Fraud Risk Engine
Provides:
- Controlled Payment Lifecycle State Machine (CREATED -> INITIATED -> PENDING -> SUCCESS/FAILED/CANCELLED -> REFUND_PENDING -> PARTIALLY_REFUNDED/REFUNDED/DISPUTED)
- Multi-signal transaction risk scoring (failed velocity, rapid burst, high-value, refund velocity)
- Never permanently bans users solely from automated risk score
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

TX_STATES = {
    "CREATED",
    "INITIATED",
    "PENDING",
    "SUCCESS",
    "FAILED",
    "CANCELLED",
    "REFUND_PENDING",
    "PARTIALLY_REFUNDED",
    "REFUNDED",
    "DISPUTED",
}

VALID_TX_TRANSITIONS: Dict[str, set] = {
    "CREATED": {"INITIATED", "FAILED", "CANCELLED"},
    "INITIATED": {"PENDING", "SUCCESS", "FAILED", "CANCELLED"},
    "PENDING": {"SUCCESS", "FAILED", "CANCELLED"},
    "SUCCESS": {"REFUND_PENDING", "PARTIALLY_REFUNDED", "REFUNDED", "DISPUTED"},
    "FAILED": set(),
    "CANCELLED": set(),
    "REFUND_PENDING": {"PARTIALLY_REFUNDED", "REFUNDED", "FAILED"},
    "PARTIALLY_REFUNDED": {"REFUND_PENDING", "REFUNDED", "DISPUTED"},
    "REFUNDED": {"DISPUTED"},
    "DISPUTED": {"SUCCESS", "REFUNDED", "PARTIALLY_REFUNDED"},
}


def validate_tx_transition(current_state: str, new_state: str) -> bool:
    cur = (current_state or "").upper()
    nxt = (new_state or "").upper()
    if cur not in TX_STATES or nxt not in TX_STATES:
        return False
    return nxt in VALID_TX_TRANSITIONS.get(cur, set())


async def evaluate_transaction_risk(
    db,
    user_id: str,
    amount_paise: int,
    recipient_identifier: str,
) -> Dict[str, Any]:
    """
    Evaluates transaction risk based on recent velocity, failed attempts, and amount thresholds.
    Returns {score, action: ALLOW|FLAG_REVIEW|HOLD, signals}.
    """
    if db is None:
        return {"score": 0.0, "action": "ALLOW", "signals": []}

    now = datetime.now(timezone.utc)
    score = 0.0
    signals: List[str] = []

    # 1. Repeated failed transactions in last 15 minutes
    since_15m = now - timedelta(minutes=15)
    failed_count = await db.payment_transactions.count_documents({
        "user_id": user_id,
        "status": "failed",
        "created_at": {"$gte": since_15m},
    })
    if failed_count >= 3:
        score = max(score, 0.80)
        signals.append(f"repeated_failures_15m:{failed_count}")

    # 2. Rapid burst (> 5 transactions in 5 minutes)
    since_5m = now - timedelta(minutes=5)
    recent_count = await db.payment_transactions.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": since_5m},
    })
    if recent_count >= 5:
        score = max(score, 0.70)
        signals.append(f"rapid_velocity_5m:{recent_count}")

    # 3. High-value transaction check (> Rs 50,000 = 5,000,000 paise)
    if amount_paise >= 5_000_000:
        score = max(score, 0.55)
        signals.append("high_value_tx")

    # 4. Refund abuse velocity (> 3 refunds in 24h)
    since_24h = now - timedelta(hours=24)
    refund_count = await db.payment_refunds.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": since_24h},
    })
    if refund_count >= 3:
        score = max(score, 0.65)
        signals.append(f"high_refund_velocity_24h:{refund_count}")

    if score >= 0.80:
        action = "HOLD"
    elif score >= 0.50:
        action = "FLAG_REVIEW"
    else:
        action = "ALLOW"

    return {"score": round(score, 3), "action": action, "signals": signals}
