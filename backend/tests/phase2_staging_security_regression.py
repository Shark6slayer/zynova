import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from bson import ObjectId
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.security import get_password_hash, create_access_token
from app.core.otp_service import OTPService

BASE_URL = "http://127.0.0.1:8001"
results = []

def record(phase, case_id, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((phase, case_id, name, status, detail))
    print(f"[{status}] {phase} | {case_id}: {name} -> {detail}")

async def seed_user(db, email, username, full_name, phone=None):
    await db.users.delete_many({"email": email})
    await db.users.delete_many({"username": username})
    doc = {
        "email": email,
        "username": username,
        "zen_id": username,
        "full_name": full_name,
        "hashed_password": get_password_hash("ZenovaTestPass#2026"),
        "is_active": True,
        "is_verified": True,
        "phone_verified": True,
        "phone_number": phone,
        "account_status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    token = create_access_token({"sub": uid, "email": email, "type": "access"})
    return uid, token

async def run_suite():
    await connect_to_database()
    db = get_database()
    assert db is not None, "Staging DB connection required"
    assert db.name == "zenova_staging_db", f"Safety abort: connected to {db.name}"

    alice_id, alice_tok = await seed_user(db, "p2_alice@staging.zenova.in", "p2_alice", "Phase2 Alice", "+919000000001")
    bob_id, bob_tok = await seed_user(db, "p2_bob@staging.zenova.in", "p2_bob", "Phase2 Bob", "+919000000002")
    charlie_id, charlie_tok = await seed_user(db, "p2_charlie@staging.zenova.in", "p2_charlie", "Phase2 Charlie", "+919000000003")

    h_alice = {"Authorization": f"Bearer {alice_tok}"}
    h_bob = {"Authorization": f"Bearer {bob_tok}"}
    h_charlie = {"Authorization": f"Bearer {charlie_tok}"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        # --- PHASE 2.1: SOCIAL ---
        r = await client.post("/api/v1/social/posts", headers=h_alice, json={"content": "Phase2 Staging Post"})
        post_id = r.json().get("id") if r.status_code == 201 else None
        record("2.1-Social", "SOC-01", "Create Social Post", r.status_code == 201 and bool(post_id), f"HTTP {r.status_code}")

        r = await client.get("/api/v1/social/feed?mode=discovery&limit=10&skip=0", headers=h_bob)
        record("2.1-Social", "SOC-02", "Load Discovery Feed & Pagination", r.status_code == 200, f"HTTP {r.status_code}")

        if post_id:
            r = await client.post(f"/api/v1/social/posts/{post_id}/like", headers=h_bob)
            record("2.1-Social", "SOC-03", "Like Post", r.status_code == 200, f"HTTP {r.status_code}")

            r = await client.post(f"/api/v1/social/posts/{post_id}/comments", headers=h_bob, json={"content": "Nice post!"})
            record("2.1-Social", "SOC-04", "Comment on Post", r.status_code == 201, f"HTTP {r.status_code}")

        # --- PHASE 2.1: ZENOVA PAY ---
        r = await client.get("/api/v1/payments/accounts", headers=h_alice)
        record("2.1-Pay", "PAY-01", "Bank Accounts Endpoint Load", r.status_code == 200, f"HTTP {r.status_code}")

        r = await client.get("/api/v1/payments/rupay-cards", headers=h_alice)
        record("2.1-Pay", "PAY-02", "RuPay Cards Endpoint Load", r.status_code == 200, f"HTTP {r.status_code}")

        r = await client.get("/api/v1/payments/transactions", headers=h_alice)
        record("2.1-Pay", "PAY-03", "Transaction History Load", r.status_code == 200, f"HTTP {r.status_code}")

        r = await client.get("/api/v1/payments/accounts")
        record("2.1-Pay", "PAY-04", "Unauthorized Payment Access Blocked", r.status_code == 401, f"HTTP {r.status_code}")

        # --- PHASE 2.1: ACCOUNT MANAGEMENT & LEGAL ---
        r = await client.patch("/api/v1/users/me", headers=h_alice, json={"bio": "Staging bio updated"})
        record("2.1-Account", "ACC-01", "Profile Update (PATCH /users/me)", r.status_code == 200, f"HTTP {r.status_code}")

        r = await client.get("/api/v1/account/deletion/status", headers=h_alice)
        record("2.1-Account", "ACC-02", "Account Deletion Status Check", r.status_code == 200 and r.json().get("account_status") == "active", f"HTTP {r.status_code}")

        for path, name in [("/privacy", "Privacy Policy"), ("/terms", "Terms of Service"), ("/delete-account", "Account Deletion Portal")]:
            r = await client.get(path)
            record("2.1-Legal", f"LEG-{path[1:4].upper()}", f"{name} Endpoint", r.status_code == 200 and "ZENOVA" in r.text, f"HTTP {r.status_code}")

        # --- PHASE 2.2: AUTHENTICATION & API SECURITY ---
        r = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid.tampered.jwt"})
        record("2.2-Auth", "SEC-AUTH-01", "Tampered JWT Rejected", r.status_code == 401, f"HTTP {r.status_code}")

        r = await client.get("/api/v1/health")
        sec_headers = all(h in r.headers for h in ["x-content-type-options", "x-frame-options", "referrer-policy"])
        record("2.2-API", "SEC-API-01", "Security Headers Present", sec_headers, f"X-Frame={r.headers.get('x-frame-options')}, X-CTO={r.headers.get('x-content-type-options')}")

        r = await client.get("/api/v1/chat/users/search?q[$ne]=1", headers=h_alice)
        record("2.2-API", "SEC-API-02", "Query Injection Resilience", r.status_code in (200, 400, 422), f"HTTP {r.status_code}")

        if post_id:
            r = await client.delete(f"/api/v1/social/posts/{post_id}", headers=h_bob)
            record("2.2-API", "SEC-API-03", "IDOR Post Delete Blocked", r.status_code in (403, 404), f"HTTP {r.status_code}")

        # --- PHASE 2.2: BIDIRECTIONAL BLOCKING (A blocks B AND B blocks A independently) ---
        await client.post(f"/api/v1/platform/users/{bob_id}/block", headers=h_alice)
        await client.post(f"/api/v1/platform/users/{alice_id}/block", headers=h_bob)
        await client.delete(f"/api/v1/platform/users/{bob_id}/block", headers=h_alice)
        r = await client.post("/api/v1/chat/conversations", headers=h_alice, json={"recipient_id": bob_id})
        record("2.2-Block", "SEC-BLK-01", "Asymmetric Unblock Preserves Reverse Block", r.status_code == 403, f"HTTP {r.status_code}")
        await client.delete(f"/api/v1/platform/users/{alice_id}/block", headers=h_bob)

        # --- PHASE 2.2: UGC REPORTING ---
        if post_id:
            r = await client.post("/api/v1/social/reports", headers=h_charlie, json={"target_type": "post", "target_id": post_id, "reason": "Harassment or bullying", "description": "Valid staging report"})
            r_dup = await client.post("/api/v1/social/reports", headers=h_charlie, json={"target_type": "post", "target_id": post_id, "reason": "Harassment or bullying"})
            record("2.2-UGC", "SEC-UGC-01", "Valid Report & Duplicate Rejection", r.status_code == 201 and r_dup.status_code == 400, f"r1={r.status_code}, dup={r_dup.status_code}")

        # --- PHASE 2.2: OTP SECURITY (No OTP values printed) ---
        otp_email = f"p2_otp_{int(time.time())}@staging.zenova.in"
        otp_val, created, cd = await OTPService.create_email_verification_otp(otp_email)
        _, created_cd, cd_rem = await OTPService.create_email_verification_otp(otp_email)
        bad_verify = await OTPService.verify_email_otp(otp_email, "000000")
        good_verify = await OTPService.verify_email_otp(otp_email, otp_val)
        replay_verify = await OTPService.verify_email_otp(otp_email, otp_val)
        record("2.2-OTP", "SEC-OTP-01", "OTP Cooldown, Invalid, Single-Use & Replay Protection",
               created and (not created_cd) and cd_rem > 0 and (not bad_verify[0]) and good_verify[0] and (not replay_verify[0]),
               f"created={created}, cooldown_blocked={not created_cd}({cd_rem}s), invalid={bad_verify[0]}, first={good_verify[0]}, replay={replay_verify[0]}")

        # --- PHASE 2.1: ACCOUNT DELETION & RECOVERY LIFECYCLE ---
        r_del = await client.post("/api/v1/account/deletion/request", headers=h_charlie, json={"password": "ZenovaTestPass#2026", "reason": "Staging E2E"})
        record("2.1-Account", "ACC-03", "Deletion Request & 30-Day Grace Period", r_del.status_code == 200 and r_del.json().get("days_remaining") == 30, f"HTTP {r_del.status_code}")

        r_post_del = await client.get("/api/v1/users/me", headers=h_charlie)
        record("2.2-Auth", "SEC-AUTH-02", "Pending Deletion Returns 403 ACCOUNT_PENDING_DELETION", r_post_del.status_code == 403 and r_post_del.headers.get("x-error-code") == "ACCOUNT_PENDING_DELETION", f"HTTP {r_post_del.status_code}")

        await db.users.delete_one({"_id": ObjectId(charlie_id)})
        r_perm_del = await client.get("/api/v1/users/me", headers=h_charlie)
        record("2.2-Auth", "SEC-AUTH-02B", "Permanently Deleted User Token Returns 401", r_perm_del.status_code == 401, f"HTTP {r_perm_del.status_code}")

        r_logout = await client.post("/api/v1/auth/logout", headers=h_bob)
        r_after_logout = await client.get("/api/v1/users/me", headers=h_bob)
        record("2.2-Auth", "SEC-AUTH-03", "Logout Immediately Revokes Token", r_logout.status_code == 200 and r_after_logout.status_code == 401, f"logout={r_logout.status_code}, after={r_after_logout.status_code}")

    await close_database_connection()
    passed = sum(1 for x in results if x[3] == "PASS")
    print(f"\nTOTAL: {passed}/{len(results)} PASSED")

if __name__ == "__main__":
    asyncio.run(run_suite())
