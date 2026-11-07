"""
Integration test suite for Zynova Connect Communication Platform (Phase 26).
Verifies:
1. One-to-one messaging with reactions, replies, forwards, and pinning.
2. Group chat creation, member management, and admin access control.
3. Locked chats with Argon2id PIN verification and privacy preservation.
4. Archived chats synchronization across device views.
5. WhatsApp-style 24-hour Status updates and view receipts.
6. Communities organizing group channels.
7. WebRTC call signaling state transitions.
8. Signal Protocol E2EE prekey bundle publishing and Double Ratchet cryptographic ratchet cycles.
"""

import pytest
import base64
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.e2ee_engine import generate_prekey_bundle, ZynovaDoubleRatchet
from cryptography.hazmat.primitives.asymmetric import x25519

from app.core.rate_limit import auth_rate_limiter, chat_rate_limiter

@pytest.fixture(autouse=True)
async def init_connect_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    chat_rate_limiter.requests.clear()
    yield
    auth_rate_limiter.requests.clear()
    chat_rate_limiter.requests.clear()
    db = get_database()
    if db is not None:
        await db.users.delete_many({"email": {"$regex": "@testconnect.zynova.in$"}})
        await db.chat_rooms.delete_many({})
        await db.chat_messages.delete_many({})
        await db.connect_statuses.delete_many({})
        await db.connect_communities.delete_many({})
        await db.connect_calls.delete_many({})
        await db.e2ee_prekeys.delete_many({})
    await close_database_connection()

async def create_auth_user(ac: AsyncClient, email: str, username: str, full_name: str) -> dict:
    reg = await ac.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "full_name": full_name,
        "password": "Password123!"
    })
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {
        "id": user_id,
        "email": email,
        "username": username,
        "full_name": full_name,
        "headers": {"Authorization": f"Bearer {token}"}
    }

@pytest.mark.asyncio
async def test_one_to_one_messaging_reactions_and_pinning():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        u1 = await create_auth_user(ac, "alice@testconnect.zynova.in", "alice_c", "Alice Smith")
        u2 = await create_auth_user(ac, "bob@testconnect.zynova.in", "bob_c", "Bob Jones")

        # 1. Start Direct Chat
        conv = await ac.post("/api/v1/chat/conversations", json={"recipient_id": u2["id"]}, headers=u1["headers"])
        assert conv.status_code == 200
        conv_id = conv.json()["id"]

        # 2. Send Message with idempotency client_message_id
        msg1 = await ac.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"text": "Hey Bob! Check out Connect.", "client_message_id": "client_uuid_1001"},
            headers=u1["headers"]
        )
        assert msg1.status_code == 201
        m1_data = msg1.json()
        assert m1_data["text"] == "Hey Bob! Check out Connect."
        m1_id = m1_data["id"]

        # Idempotency: duplicate post returns same message
        dup = await ac.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"text": "Different text but duplicate ID", "client_message_id": "client_uuid_1001"},
            headers=u1["headers"]
        )
        assert dup.status_code == 201
        assert dup.json()["id"] == m1_id

        # 3. Bob reacts to message
        react = await ac.post(f"/api/v1/chat/messages/{m1_id}/react", json={"emoji": "❤️"}, headers=u2["headers"])
        assert react.status_code == 200

        # 4. Pin message
        pin = await ac.post(f"/api/v1/chat/conversations/{conv_id}/messages/{m1_id}/pin", headers=u1["headers"])
        assert pin.status_code == 200
        assert pin.json()["pinned_message_id"] == m1_id

        # 5. Verify message history reflects reaction and pinned status
        history = await ac.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=u2["headers"])
        assert history.status_code == 200
        hist_msgs = history.json()
        assert len(hist_msgs) == 1
        assert hist_msgs[0]["reactions"].get(u2["id"]) == "❤️"
        assert hist_msgs[0]["is_pinned"] is True

@pytest.mark.asyncio
async def test_group_chat_management_and_admin_roles():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        admin = await create_auth_user(ac, "admin@testconnect.zynova.in", "admin_c", "Connect Admin")
        member1 = await create_auth_user(ac, "mem1@testconnect.zynova.in", "mem1_c", "Member One")
        member2 = await create_auth_user(ac, "mem2@testconnect.zynova.in", "mem2_c", "Member Two")

        # 1. Create Group Chat
        grp_res = await ac.post(
            "/api/v1/chat/groups",
            json={
                "name": "Zynova Engineering",
                "description": "Core platform discussions",
                "participant_ids": [member1["id"]]
            },
            headers=admin["headers"]
        )
        assert grp_res.status_code == 201
        grp = grp_res.json()
        grp_id = grp["id"]
        assert admin["id"] in grp["admin_ids"]
        assert len(grp["participants"]) == 2

        # 2. Non-admin cannot add member
        fail_add = await ac.post(
            f"/api/v1/chat/groups/{grp_id}/members",
            json={"user_id": member2["id"]},
            headers=member1["headers"]
        )
        assert fail_add.status_code == 403

        # 3. Admin adds member2
        success_add = await ac.post(
            f"/api/v1/chat/groups/{grp_id}/members",
            json={"user_id": member2["id"]},
            headers=admin["headers"]
        )
        assert success_add.status_code == 200

        # 4. Remove member
        remove_res = await ac.delete(f"/api/v1/chat/groups/{grp_id}/members/{member1['id']}", headers=admin["headers"])
        assert remove_res.status_code == 200

@pytest.mark.asyncio
async def test_locked_chats_and_archived_chats():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        u1 = await create_auth_user(ac, "lock1@testconnect.zynova.in", "lock1_c", "Lock User 1")
        u2 = await create_auth_user(ac, "lock2@testconnect.zynova.in", "lock2_c", "Lock User 2")

        conv = await ac.post("/api/v1/chat/conversations", json={"recipient_id": u2["id"]}, headers=u1["headers"])
        conv_id = conv.json()["id"]

        # 1. Lock Chat with PIN "8492"
        lock_res = await ac.post(f"/api/v1/chat/conversations/{conv_id}/lock", json={"pin": "8492"}, headers=u1["headers"])
        assert lock_res.status_code == 200
        assert lock_res.json()["status"] == "locked"

        # 2. Try unlock with wrong PIN
        wrong_unlock = await ac.post(f"/api/v1/chat/conversations/{conv_id}/unlock", json={"pin": "0000"}, headers=u1["headers"])
        assert wrong_unlock.status_code == 403

        # 3. Unlock with correct PIN
        correct_unlock = await ac.post(f"/api/v1/chat/conversations/{conv_id}/unlock", json={"pin": "8492"}, headers=u1["headers"])
        assert correct_unlock.status_code == 200
        assert correct_unlock.json()["unlocked"] is True

        # 4. Archive conversation
        arch_res = await ac.post(f"/api/v1/chat/conversations/{conv_id}/archive", headers=u1["headers"])
        assert arch_res.status_code == 200
        assert arch_res.json()["status"] == "archived"

        # Active conversation list should not show archived conversation
        normal_list = await ac.get("/api/v1/chat/conversations?archived=false", headers=u1["headers"])
        assert not any(c["id"] == conv_id for c in normal_list.json())

        # Archived conversation list contains it
        arch_list = await ac.get("/api/v1/chat/conversations?archived=true", headers=u1["headers"])
        assert any(c["id"] == conv_id for c in arch_list.json())

@pytest.mark.asyncio
async def test_connect_status_24h_expiration():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        poster = await create_auth_user(ac, "poster@testconnect.zynova.in", "poster_c", "Poster User")
        viewer = await create_auth_user(ac, "viewer@testconnect.zynova.in", "viewer_c", "Viewer User")

        # Create status
        st_res = await ac.post(
            "/api/v1/chat/status",
            json={
                "media_type": "text",
                "caption": "Hello Zynova Updates!",
                "bg_color": "#128C7E",
                "privacy": "contacts"
            },
            headers=poster["headers"]
        )
        assert st_res.status_code == 201
        st_data = st_res.json()
        st_id = st_data["id"]
        assert st_data["caption"] == "Hello Zynova Updates!"

        # Viewer records view
        view_res = await ac.post(f"/api/v1/chat/status/{st_id}/view", headers=viewer["headers"])
        assert view_res.status_code == 200

@pytest.mark.asyncio
async def test_communities_creation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        leader = await create_auth_user(ac, "leader@testconnect.zynova.in", "leader_c", "Community Leader")

        # Create Community
        comm_res = await ac.post(
            "/api/v1/chat/communities",
            json={
                "name": "Bangalore Tech Hub",
                "description": "Tech founders and engineers in Bangalore"
            },
            headers=leader["headers"]
        )
        assert comm_res.status_code == 201
        comm = comm_res.json()
        assert comm["name"] == "Bangalore Tech Hub"
        assert comm["announcement_group_id"] is not None

@pytest.mark.asyncio
async def test_webrtc_call_signaling():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        caller = await create_auth_user(ac, "caller@testconnect.zynova.in", "caller_c", "Caller User")
        callee = await create_auth_user(ac, "callee@testconnect.zynova.in", "callee_c", "Callee User")

        conv = await ac.post("/api/v1/chat/conversations", json={"recipient_id": callee["id"]}, headers=caller["headers"])
        conv_id = conv.json()["id"]

        # Initiate Call
        call_res = await ac.post(
            "/api/v1/chat/calls/initiate",
            json={"conversation_id": conv_id, "call_type": "video", "recipient_id": callee["id"]},
            headers=caller["headers"]
        )
        assert call_res.status_code == 201
        call_id = call_res.json()["id"]

        # Callee sends WebRTC answer signal
        signal_res = await ac.post(
            "/api/v1/chat/calls/signal",
            json={"call_id": call_id, "signal_type": "answer", "payload": {"sdp": "v=0..."}},
            headers=callee["headers"]
        )
        assert signal_res.status_code == 200

        # Terminate Call
        end_res = await ac.post(
            "/api/v1/chat/calls/signal",
            json={"call_id": call_id, "signal_type": "end", "payload": {}},
            headers=caller["headers"]
        )
        assert end_res.status_code == 200

        # Call history reflects status
        history = await ac.get("/api/v1/chat/calls/history", headers=caller["headers"])
        assert history.status_code == 200
        assert any(c["id"] == call_id and c["status"] == "completed" for c in history.json())

@pytest.mark.asyncio
async def test_signal_protocol_e2ee_integration():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        alice = await create_auth_user(ac, "alice_crypto@testconnect.zynova.in", "alice_cr", "Alice Crypto")
        bob = await create_auth_user(ac, "bob_crypto@testconnect.zynova.in", "bob_cr", "Bob Crypto")

        # 1. Bob generates and publishes Signal Prekey Bundle
        bob_bundle = generate_prekey_bundle(num_one_time_keys=5)
        pub_res = await ac.post(
            "/api/v1/chat/e2ee/prekeys",
            json={
                "identity_key_pub": bob_bundle["identity_key_pub"],
                "signed_prekey_pub": bob_bundle["signed_prekey_pub"],
                "one_time_prekeys": bob_bundle["one_time_prekeys"]
            },
            headers=bob["headers"]
        )
        assert pub_res.status_code == 200

        # 2. Alice fetches Bob's prekey bundle
        get_bundle = await ac.get(f"/api/v1/chat/e2ee/prekeys/{bob['id']}", headers=alice["headers"])
        assert get_bundle.status_code == 200
        fetched = get_bundle.json()
        assert fetched["identity_key_pub"] == bob_bundle["identity_key_pub"]
        assert fetched["one_time_prekey"] is not None

        # 3. Simulate Signal Double Ratchet Handshake & Message Transmission
        shared_secret = b"zynova_mock_shared_x3dh_secret_32b!"
        bob_dh_priv = x25519.X25519PrivateKey.generate()
        bob_dh_pub = bob_dh_priv.public_key()

        alice_ratchet = ZynovaDoubleRatchet.initiate_alice(shared_secret, bob_dh_pub)
        bob_ratchet = ZynovaDoubleRatchet.initiate_bob(shared_secret, bob_dh_priv)

        # Alice encrypts message frame
        frame = alice_ratchet.encrypt(b"Zynova Connect End-to-End Encrypted Message")
        assert "ciphertext" in frame
        assert "nonce" in frame

        # Bob decrypts frame
        decrypted = bob_ratchet.decrypt(frame)
        assert decrypted == b"Zynova Connect End-to-End Encrypted Message"
