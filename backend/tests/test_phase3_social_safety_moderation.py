import asyncio
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.security import create_access_token, get_password_hash


@pytest.fixture(autouse=True)
async def setup_db():
    await connect_to_database()
    yield
    await close_database_connection()


async def _seed_user(db, email, username, role="regular"):
    await db.users.delete_many({"email": email})
    await db.users.delete_many({"username": username})
    res = await db.users.insert_one({
        "email": email,
        "username": username,
        "zen_id": username,
        "full_name": username,
        "role": role,
        "hashed_password": get_password_hash("SafetyTest#2026"),
        "is_active": True,
        "is_verified": True,
        "account_status": "active",
        "created_at": datetime.now(timezone.utc),
    })
    uid = str(res.inserted_id)
    tok = create_access_token({"sub": uid, "email": email, "type": "access"})
    return uid, tok


@pytest.mark.asyncio
async def test_phase3_reporting_moderation_rbac_appeals_and_abuse():
    db = get_database()
    u1_id, u1_tok = await _seed_user(db, "p3_user1@zenova.test", "p3_user1", role="regular")
    u2_id, u2_tok = await _seed_user(db, "p3_user2@zenova.test", "p3_user2", role="regular")
    mod_id, mod_tok = await _seed_user(db, "p3_mod@zenova.test", "p3_mod", role="moderator")
    smod_id, smod_tok = await _seed_user(db, "p3_smod@zenova.test", "p3_smod", role="senior_moderator")

    await db.reports.delete_many({"reporter_id": {"$in": [u1_id, u2_id]}})
    await db.safety_appeals.delete_many({"user_id": {"$in": [u1_id, u2_id]}})
    await db.account_enforcements.delete_many({"user_id": {"$in": [u1_id, u2_id]}})
    await db.moderation_content_hashes.delete_many({"user_id": {"$in": [u1_id, u2_id]}})
    await db.posts.delete_many({"author_id": {"$in": [u1_id, u2_id]}})

    h_u1 = {"Authorization": f"Bearer {u1_tok}"}
    h_u2 = {"Authorization": f"Bearer {u2_tok}"}
    h_mod = {"Authorization": f"Bearer {mod_tok}"}
    h_smod = {"Authorization": f"Bearer {smod_tok}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Safe post allowed & visible in feed
        r_safe = await ac.post("/api/v1/social/posts", headers=h_u1, json={"content": "Hello ZENOVA community!"})
        assert r_safe.status_code == 201
        safe_post_id = r_safe.json()["id"]

        # 2. Unsafe scam/malicious URL post quarantined & hidden from discovery feed
        r_unsafe = await ac.post("/api/v1/social/posts", headers=h_u1, json={"content": "Send OTP now at http://192.168.1.50/phish"})
        assert r_unsafe.status_code == 201
        unsafe_post_id = r_unsafe.json()["id"]

        r_feed = await ac.get("/api/v1/social/feed?mode=discovery&limit=50", headers=h_u2)
        assert r_feed.status_code == 200
        feed_ids = [p["id"] for p in r_feed.json()]
        assert safe_post_id in feed_ids
        assert unsafe_post_id not in feed_ids

        # 3. Duplicate spam burst detection (3 identical posts -> 4th rejected with 429)
        for i in range(3):
            r_dup = await ac.post("/api/v1/social/posts", headers=h_u2, json={"content": "Identical spam burst text"})
            assert r_dup.status_code == 201
        r_burst = await ac.post("/api/v1/social/posts", headers=h_u2, json={"content": "Identical spam burst text"})
        assert r_burst.status_code == 429

        # 4. Social message malicious link blocked
        r_msg_bad = await ac.post("/api/v1/social/messages/send", headers=h_u2, json={
            "recipient_zen_id": "p3_user1",
            "text": "Click http://10.0.0.1/steal-pin and send otp",
        })
        assert r_msg_bad.status_code == 400

        # 5. Reporting: invalid category (422), valid report (201), duplicate (400), ownership isolation
        r_inv = await ac.post("/api/v1/safety/reports", headers=h_u2, json={"target_type": "post", "target_id": safe_post_id, "category": "invalid_cat"})
        assert r_inv.status_code == 422

        r_rep = await ac.post("/api/v1/safety/reports", headers=h_u2, json={
            "target_type": "post", "target_id": safe_post_id, "category": "harassment", "description": "Test report"
        })
        assert r_rep.status_code == 201
        report_id = r_rep.json()["id"]
        assert r_rep.json()["status"] == "PENDING"

        r_rep_dup = await ac.post("/api/v1/safety/reports", headers=h_u2, json={
            "target_type": "post", "target_id": safe_post_id, "category": "harassment"
        })
        assert r_rep_dup.status_code == 400

        # Ownership isolation: u1 cannot see u2's submitted reports
        r_u1_reps = await ac.get("/api/v1/safety/reports/me", headers=h_u1)
        assert all(x["id"] != report_id for x in r_u1_reps.json())

        # 6. RBAC: regular user blocked from moderator endpoints (403)
        assert (await ac.get("/api/v1/moderation/queue", headers=h_u1)).status_code == 403
        assert (await ac.post(f"/api/v1/moderation/reports/{report_id}/action", headers=h_u1, json={"action": "dismiss", "reason": "Hacked"})).status_code == 403

        # 7. Moderator queue & state machine transition
        assert (await ac.get("/api/v1/moderation/queue", headers=h_mod)).status_code == 200
        r_tr = await ac.post(f"/api/v1/moderation/reports/{report_id}/transition", headers=h_mod, json={"new_status": "UNDER_REVIEW", "note": "Investigating"})
        assert r_tr.status_code == 200 and r_tr.json()["status"] == "UNDER_REVIEW"

        # Invalid state transition (e.g., invalid status)
        assert (await ac.post(f"/api/v1/moderation/reports/{report_id}/transition", headers=h_mod, json={"new_status": "BOGUS"})).status_code == 422

        # Moderator cannot issue permanent_suspension (requires senior_moderator/admin)
        r_perm_try = await ac.post(f"/api/v1/moderation/reports/{report_id}/action", headers=h_mod, json={
            "action": "suspend_account", "enforcement_tier": "permanent_suspension", "reason": "Escalated abuse"
        })
        assert r_perm_try.status_code == 403

        # Moderator cannot read audit logs (senior_moderator/admin only)
        assert (await ac.get("/api/v1/moderation/audit-logs", headers=h_mod)).status_code == 403
        assert (await ac.get("/api/v1/moderation/audit-logs", headers=h_smod)).status_code == 200

        # 8. Moderator restricts content & warns user -> User appeals -> Senior Mod approves & restores
        r_act = await ac.post(f"/api/v1/moderation/reports/{report_id}/action", headers=h_mod, json={
            "action": "restrict_content", "reason": "Policy violation"
        })
        assert r_act.status_code == 200 and r_act.json()["status"] == "RESOLVED"

        r_app = await ac.post("/api/v1/safety/appeals", headers=h_u1, json={
            "target_type": "content", "target_id": safe_post_id, "reason": "This was a false positive, please review."
        })
        assert r_app.status_code == 201
        appeal_id = r_app.json()["id"]

        r_rev = await ac.post(f"/api/v1/moderation/appeals/{appeal_id}/review", headers=h_smod, json={
            "decision": "approve", "reasoning": "Reviewed context; content is compliant."
        })
        assert r_rev.status_code == 200 and r_rev.json()["status"] == "APPROVED"

        # Content is restored in discovery feed
        r_feed_after = await ac.get("/api/v1/social/feed?mode=discovery&limit=50", headers=h_u2)
        assert safe_post_id in [p["id"] for p in r_feed_after.json()]

        # User standing & policies endpoint
        assert (await ac.get("/api/v1/safety/policies")).status_code == 200
        assert (await ac.get("/api/v1/safety/account-standing", headers=h_u1)).status_code == 200
