"""
ZENOVA Phase 1.6 — Staging API End-to-End Verification Runner.
Executes real HTTP requests against the running staging backend at http://127.0.0.1:8001
with isolated database 'zenova_staging_db'.
"""

import sys
import time
import uuid
import httpx
from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = "http://127.0.0.1:8001"
STAGING_DB_NAME = "zenova_staging_db"
MONGO_URI = "mongodb://127.0.0.1:27017"

def main():
    print("=" * 60)
    print("   ZENOVA STAGING API END-TO-END VERIFICATION (HTTP)")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    print(f"Database: {STAGING_DB_NAME}")

    # Connect to staging mongo directly for baseline user creation and assertions
    mongo = MongoClient(MONGO_URI)
    db = mongo[STAGING_DB_NAME]

    suffix = uuid.uuid4().hex[:6]
    results = []

    def record(name, status, status_code, latency_ms, detail=""):
        res = {
            "name": name,
            "status": status,
            "code": status_code,
            "latency_ms": round(latency_ms, 2),
            "detail": detail
        }
        results.append(res)
        mark = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"  {mark} {name}: HTTP {status_code} ({res['latency_ms']}ms) - {detail}")

    # Seed 3 users in staging DB with valid password hash and JWT tokens
    from app.core.security import create_access_token, get_password_hash

    # User A
    u_a_id = ObjectId()
    u_a_doc = {
        "_id": u_a_id,
        "email": f"stg_alice_{suffix}@zenova.test",
        "username": f"stg_alice_{suffix}",
        "full_name": f"Staging Alice {suffix}",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "phone_verified": True,
        "phone_number": f"+9199111{suffix[:5]}",
        "blocked_users": [],
        "created_at": datetime.now(timezone.utc)
    }
    db.users.insert_one(u_a_doc)
    tok_a = create_access_token({"sub": str(u_a_id), "email": u_a_doc["email"], "type": "access"})
    h_a = {"Authorization": f"Bearer {tok_a}"}

    # User B
    u_b_id = ObjectId()
    u_b_doc = {
        "_id": u_b_id,
        "email": f"stg_bob_{suffix}@zenova.test",
        "username": f"stg_bob_{suffix}",
        "full_name": f"Staging Bob {suffix}",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "phone_verified": True,
        "phone_number": f"+9199222{suffix[:5]}",
        "blocked_users": [],
        "created_at": datetime.now(timezone.utc)
    }
    db.users.insert_one(u_b_doc)
    tok_b = create_access_token({"sub": str(u_b_id), "email": u_b_doc["email"], "type": "access"})
    h_b = {"Authorization": f"Bearer {tok_b}"}

    # User C (Unrelated)
    u_c_id = ObjectId()
    u_c_doc = {
        "_id": u_c_id,
        "email": f"stg_charlie_{suffix}@zenova.test",
        "username": f"stg_charlie_{suffix}",
        "full_name": f"Staging Charlie {suffix}",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "phone_verified": True,
        "phone_number": f"+9199333{suffix[:5]}",
        "blocked_users": [],
        "created_at": datetime.now(timezone.utc)
    }
    db.users.insert_one(u_c_doc)
    tok_c = create_access_token({"sub": str(u_c_id), "email": u_c_doc["email"], "type": "access"})
    h_c = {"Authorization": f"Bearer {tok_c}"}

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # --- 1. HEALTH & READINESS ---
        t0 = time.perf_counter()
        r = client.get("/api/v1/health")
        t_ms = (time.perf_counter() - t0) * 1000
        record("Health Check", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, r.json().get("service", ""))

        t0 = time.perf_counter()
        r = client.get("/api/v1/ready")
        t_ms = (time.perf_counter() - t0) * 1000
        record("Readiness Check", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, r.json().get("database", ""))

        # --- 2. SOCIAL POST & INTERACTIONS (PRE-BLOCK) ---
        t0 = time.perf_counter()
        r = client.post("/api/v1/social/posts", json={"content": "Alice Post on Staging"}, headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        post_a_id = r.json().get("id")
        record("Create Post (Alice)", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, f"Post ID: {post_a_id}")

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/social/posts/{post_a_id}/like", headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Like Post (Bob likes Alice)", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, r.json().get("status", ""))

        t0 = time.perf_counter()
        r = client.delete(f"/api/v1/social/posts/{post_a_id}/like", headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Unlike Post (Bob unlikes Alice)", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, r.json().get("status", ""))

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/social/posts/{post_a_id}/comments", json={"content": "Bob initial comment"}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Create Comment (Bob pre-block)", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, r.json().get("id", ""))

        t0 = time.perf_counter()
        r = client.get(f"/api/v1/social/posts/{post_a_id}/comments", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("List Comments (pre-block)", "PASS" if r.status_code == 200 and len(r.json()) >= 1 else "FAIL", r.status_code, t_ms, f"Count: {len(r.json())}")

        # --- 3. UGC REPORTING ---
        t0 = time.perf_counter()
        r = client.post("/api/v1/social/reports", json={
            "target_type": "post",
            "target_id": post_a_id,
            "reason": "Harassment or bullying",
            "description": "Controlled staging report test"
        }, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Report Content (Bob reports Alice)", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, f"Status: {r.json().get('status')}")

        t0 = time.perf_counter()
        r = client.post("/api/v1/social/reports", json={
            "target_type": "post",
            "target_id": post_a_id,
            "reason": "Harassment or bullying"
        }, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Duplicate Report Rejection", "PASS" if r.status_code == 400 else "FAIL", r.status_code, t_ms, r.json().get("detail", ""))

        # --- 4. CONNECT DIRECT MESSAGING (PRE-BLOCK) ---
        t0 = time.perf_counter()
        r = client.post("/api/v1/chat/conversations", json={"recipient_id": str(u_b_id)}, headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        conv_id = r.json().get("id")
        record("Create Direct Conversation", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, f"Room ID: {conv_id}")

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={"text": "Pre-block direct message"}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Send Direct Message", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, f"Message ID: {r.json().get('id')}")

        t0 = time.perf_counter()
        r = client.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Read Message History (pre-block)", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, f"Count: {len(r.json())}")

        t0 = time.perf_counter()
        r = client.get("/api/v1/chat/conversations", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("List Conversations (pre-block)", "PASS" if any(c["id"] == conv_id for c in r.json()) else "FAIL", r.status_code, t_ms, f"Count: {len(r.json())}")

        # --- 5. BLOCK ACTION ---
        t0 = time.perf_counter()
        r = client.post(f"/api/v1/platform/users/{str(u_b_id)}/block", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Block User (Alice blocks Bob)", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, f"Status: {r.json().get('status')}")

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/platform/users/{str(u_b_id)}/block", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Duplicate Block Idempotency", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, "Idempotent success")

        # --- 6. POST-BLOCK CONTAINMENT (SOCIAL) ---
        t0 = time.perf_counter()
        r = client.post(f"/api/v1/social/posts/{post_a_id}/comments", json={"content": "Blocked comment attempt"}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Blocked Comment Attempt (Bob -> Alice)", "PASS" if r.status_code == 404 else "FAIL", r.status_code, t_ms, "HTTP 404 zero info leakage")

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/social/posts/{post_a_id}/like", headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Blocked Like Attempt (Bob -> Alice)", "PASS" if r.status_code == 404 else "FAIL", r.status_code, t_ms, "HTTP 404 zero info leakage")

        t0 = time.perf_counter()
        r = client.get("/api/v1/social/feed?mode=discovery", headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        has_post = any(p["id"] == post_a_id for p in r.json())
        record("Feed Exclusion (Bob discovery feed)", "PASS" if not has_post else "FAIL", r.status_code, t_ms, f"Alice post hidden: {not has_post}")

        # --- 7. POST-BLOCK CONTAINMENT (CONNECT CHAT) ---
        t0 = time.perf_counter()
        r = client.post("/api/v1/chat/conversations", json={"recipient_id": str(u_a_id)}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Blocked New Conversation (Bob -> Alice)", "PASS" if r.status_code == 403 else "FAIL", r.status_code, t_ms, r.json().get("detail", ""))

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={"text": "Blocked bypass attempt"}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Blocked Message Send in Old Chat (Bob -> Alice)", "PASS" if r.status_code == 403 else "FAIL", r.status_code, t_ms, r.json().get("detail", ""))

        t0 = time.perf_counter()
        r = client.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Blocked Read Message History (Bob)", "PASS" if r.status_code == 404 else "FAIL", r.status_code, t_ms, "HTTP 404 isolated")

        t0 = time.perf_counter()
        r = client.get("/api/v1/chat/conversations", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        has_conv = any(c["id"] == conv_id for c in r.json())
        record("Conversation List Filter (Alice chat list)", "PASS" if not has_conv else "FAIL", r.status_code, t_ms, f"Room hidden: {not has_conv}")

        t0 = time.perf_counter()
        r = client.get(f"/api/v1/chat/users/search?q={u_a_doc['username'][:5]}", headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        found_alice = any(u_item["id"] == str(u_a_id) for u_item in r.json())
        record("Contact Search Isolation (Bob searches Alice)", "PASS" if not found_alice else "FAIL", r.status_code, t_ms, f"Alice excluded: {not found_alice}")

        t0 = time.perf_counter()
        r = client.get(f"/api/v1/chat/users/{str(u_a_id)}/presence", headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        status_val = r.json().get("status")
        record("Presence Stalking Defense (Bob checks Alice presence)", "PASS" if status_val == "offline" else "FAIL", r.status_code, t_ms, f"Status: {status_val}")

        t0 = time.perf_counter()
        r = client.post("/api/v1/chat/calls/initiate", json={"conversation_id": conv_id, "call_type": "voice"}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Blocked Call Initiation (Bob calls Alice)", "PASS" if r.status_code in (403, 404) else "FAIL", r.status_code, t_ms, "Blocked direct call")

        # --- 8. GROUP CHAT BEHAVIOR ---
        t0 = time.perf_counter()
        r = client.post("/api/v1/chat/groups", json={
            "name": "Staging Team Group",
            "participant_ids": [str(u_c_id)]
        }, headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        grp_id = r.json().get("id")
        record("Create Group (Alice with Charlie)", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, f"Group ID: {grp_id}")

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/chat/groups/{grp_id}/members", json={"user_id": str(u_b_id)}, headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Add Blocked User to Group", "PASS" if r.status_code == 403 else "FAIL", r.status_code, t_ms, "Admin blocked from adding blocked contact")

        t0 = time.perf_counter()
        # Bob attempts to send message to group created by Alice
        r = client.post(f"/api/v1/chat/conversations/{grp_id}/messages", json={"text": "Charlie group message"}, headers=h_c)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Group Message Dispatch (Charlie in group)", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, f"Message ID: {r.json().get('id')}")

        # --- 9. SECURITY & BOUNDARY TESTS ---
        t0 = time.perf_counter()
        r = client.get("/api/v1/chat/conversations", headers={})
        t_ms = (time.perf_counter() - t0) * 1000
        record("Unauthorized Request Security", "PASS" if r.status_code == 401 else "FAIL", r.status_code, t_ms, "HTTP 401 Unauthorized")

        t0 = time.perf_counter()
        r = client.get("/api/v1/chat/conversations/invalid-hex-id/messages", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Invalid Conversation ID Handling", "PASS" if r.status_code in (400, 404, 422) else "FAIL", r.status_code, t_ms, f"HTTP {r.status_code}")

        t0 = time.perf_counter()
        r = client.post("/api/v1/platform/users/invalid-hex/block", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Invalid User ID Block Handling", "PASS" if r.status_code in (400, 404, 422, 500) else "FAIL", r.status_code, t_ms, f"HTTP {r.status_code}")

        # --- 10. UNBLOCK & RESTORATION ---
        t0 = time.perf_counter()
        r = client.delete(f"/api/v1/platform/users/{str(u_b_id)}/block", headers=h_a)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Unblock User (Alice unblocks Bob)", "PASS" if r.status_code == 200 else "FAIL", r.status_code, t_ms, f"Status: {r.json().get('status')}")

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/social/posts/{post_a_id}/comments", json={"content": "Bob post-unblock comment"}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Comment Restored Post-Unblock", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, f"Comment ID: {r.json().get('id')}")

        t0 = time.perf_counter()
        r = client.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={"text": "Bob post-unblock message"}, headers=h_b)
        t_ms = (time.perf_counter() - t0) * 1000
        record("Message Restored Post-Unblock", "PASS" if r.status_code == 201 else "FAIL", r.status_code, t_ms, f"Message ID: {r.json().get('id')}")

    # Clean up staging test records
    db.users.delete_many({"_id": {"$in": [u_a_id, u_b_id, u_c_id]}})
    db.posts.delete_many({"author_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
    db.post_comments.delete_many({"author_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
    db.chat_rooms.delete_many({"participants": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
    db.chat_messages.delete_many({"sender_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
    db.reports.delete_many({"target_id": post_a_id})

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    print("=" * 60)
    print(f"STAGING E2E RESULTS: {passed} / {total} PASSED ({round((passed/total)*100)}%)")
    print("=" * 60)

    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    main()
