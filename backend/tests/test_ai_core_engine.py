import pytest
import uuid
from bson import ObjectId
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, get_database
from app.core.security import create_access_token
from app.core.config import settings

@pytest.fixture(autouse=True)
async def ai_test_db_lifecycle():
    await connect_to_database()
    yield
    db = get_database()
    if db is not None:
        await db.ai_conversations.delete_many({"user_id": {"$regex": "^test_ai_"}})

@pytest.mark.asyncio
async def test_ai_models_endpoint_unauthenticated():
    """Verify that models metadata endpoint is public and indicates mock sandbox status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/ai/models")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        models = data["models"]
        assert len(models) >= 1
        # Mock provider must exist
        mock_model = next((m for m in models if m["provider"] == "mock"), None)
        assert mock_model is not None
        assert mock_model["is_sandbox"] is True

@pytest.mark.asyncio
async def test_ai_mock_safety_rejection_when_disabled():
    """Verify that if AI_MOCK_MODE=False, attempting to invoke the mock provider raises 403."""
    orig_mock_mode = settings.AI_MOCK_MODE
    settings.AI_MOCK_MODE = False

    db = get_database()
    user_oid = ObjectId()
    user_id = str(user_oid)
    rand_suffix = uuid.uuid4().hex[:8]

    await db.users.insert_one({
        "_id": user_oid,
        "email": f"test_ai_safety_{user_id}@example.com",
        "username": f"safety_tester_{rand_suffix}",
        "is_active": True
    })

    token = create_access_token(data={"sub": user_id, "username": f"safety_tester_{rand_suffix}"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "prompt": "Testing mock safety boundary",
                "provider": "mock",
                "model": "mock-indic-v1"
            }
            res = await client.post("/api/v1/ai/chat/stream", json=payload, headers=headers)
            assert res.status_code == 403
            data = res.json()["detail"]
            assert data["error_code"] == "MOCK_DISABLED_IN_PROD"
    finally:
        settings.AI_MOCK_MODE = orig_mock_mode
        await db.users.delete_one({"_id": user_oid})

@pytest.mark.asyncio
async def test_ai_unconfigured_real_provider_honest_rejection(monkeypatch):
    """Verify that requesting an unconfigured provider (e.g. Gemini without key) raises 401 honest rejection."""
    from app.services.ai_engine_service import ai_engine_service

    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    if "gemini" in ai_engine_service.providers:
        monkeypatch.setattr(ai_engine_service.providers["gemini"], "api_key", None)
    db = get_database()
    user_oid = ObjectId()
    user_id = str(user_oid)
    rand_suffix = uuid.uuid4().hex[:8]

    await db.users.insert_one({
        "_id": user_oid,
        "email": f"test_ai_honest_{user_id}@example.com",
        "username": f"honest_tester_{rand_suffix}",
        "is_active": True
    })

    token = create_access_token(data={"sub": user_id, "username": f"honest_tester_{rand_suffix}"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "prompt": "Testing real provider unconfigured state",
            "provider": "gemini",
            "model": "gemini-2.5-flash"
        }
        res = await client.post("/api/v1/ai/chat/stream", json=payload, headers=headers)
        # Should raise 401 AUTHENTICATION_ERROR and NEVER silently fallback to mock
        assert res.status_code == 401
        data = res.json()["detail"]
        assert data["error_code"] == "AUTHENTICATION_ERROR"
        assert "not configured" in data["message"]

    await db.users.delete_one({"_id": user_oid})

@pytest.mark.asyncio
async def test_ai_chat_streaming_lifecycle_with_explicit_mock():
    """Verify SSE streaming, token usage tracking, and conversation isolation with explicit mock enabled."""
    orig_mock_mode = settings.AI_MOCK_MODE
    settings.AI_MOCK_MODE = True

    db = get_database()
    user_oid = ObjectId()
    user_id = str(user_oid)
    rand_suffix = uuid.uuid4().hex[:8]

    await db.users.insert_one({
        "_id": user_oid,
        "email": f"test_ai_{user_id}@example.com",
        "username": f"ai_tester_{rand_suffix}",
        "is_active": True
    })

    token = create_access_token(data={"sub": user_id, "username": f"ai_tester_{rand_suffix}"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Invoke chat stream
            payload = {
                "prompt": "Hello Zynova, testing hardened AI engine",
                "provider": "mock",
                "model": "mock-indic-v1",
                "locale": "ta"
            }
            res = await client.post("/api/v1/ai/chat/stream", json=payload, headers=headers)
            assert res.status_code == 200
            assert "text/event-stream" in res.headers["content-type"]

            body = res.text
            assert "data: " in body
            assert "[Zynova Mock Sandbox]" in body
            assert '"type": "usage"' in body or '"type": "done"' in body

            # 2. List conversations
            list_res = await client.get("/api/v1/ai/conversations", headers=headers)
            assert list_res.status_code == 200
            convs = list_res.json()["conversations"]
            assert len(convs) >= 1
            conv_id = convs[0]["id"]

            # 3. Fetch details of conversation & verify token tracking
            detail_res = await client.get(f"/api/v1/ai/conversations/{conv_id}", headers=headers)
            assert detail_res.status_code == 200
            conv_data = detail_res.json()["conversation"]
            assert "total_tokens_in" in conv_data
            assert "total_tokens_out" in conv_data
            msgs = conv_data["messages"]
            assert len(msgs) >= 2
            assert msgs[0]["role"] == "user"
            assert msgs[1]["role"] == "assistant"
            assert msgs[1]["is_interrupted"] is False

            # 4. Cross-user isolation check
            other_oid = ObjectId()
            other_id = str(other_oid)
            other_suffix = uuid.uuid4().hex[:8]
            await db.users.insert_one({
                "_id": other_oid,
                "email": f"test_ai_other_{other_id}@example.com",
                "username": f"eavesdropper_{other_suffix}",
                "is_active": True
            })
            other_token = create_access_token(data={"sub": other_id, "username": f"eavesdropper_{other_suffix}"})
            other_headers = {"Authorization": f"Bearer {other_token}"}
            other_res = await client.get(f"/api/v1/ai/conversations/{conv_id}", headers=other_headers)
            assert other_res.status_code in [404, 403]

            # 5. Delete conversation
            del_res = await client.delete(f"/api/v1/ai/conversations/{conv_id}", headers=headers)
            assert del_res.status_code == 200

            await db.users.delete_many({"_id": {"$in": [user_oid, other_oid]}})
    finally:
        settings.AI_MOCK_MODE = orig_mock_mode

@pytest.mark.asyncio
async def test_zeno_agent_device_action_ack_endpoint():
    """Verify that Android device hardware acknowledgment reconciles actions via the backend route."""
    import sys
    if "C:\\zenoai" not in sys.path:
        sys.path.insert(0, "C:\\zenoai")
    from zeno_agent.tools.device_alarm import DeviceAlarmTool
    from zeno_agent.schemas.workflow import UserContext

    db = get_database()
    user_oid = ObjectId()
    user_id = str(user_oid)
    rand_suffix = uuid.uuid4().hex[:8]

    await db.users.insert_one({
        "_id": user_oid,
        "email": f"test_ai_ack_{user_id}@example.com",
        "username": f"ack_tester_{rand_suffix}",
        "is_active": True
    })

    token = create_access_token(data={"sub": user_id, "username": f"ack_tester_{rand_suffix}"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a pending action in the ledger for this user
    tool = DeviceAlarmTool()
    ctx = UserContext(user_id=user_id, username=f"ack_tester_{rand_suffix}", session_id="s1")
    exec_res = await tool.execute(
        user_context=ctx,
        parameters={"time": "08:30:00", "target_date": "tomorrow", "label": "Standup"},
        idempotency_key=f"idemp_{rand_suffix}"
    )
    action_id = exec_res["action_id"]

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 2. Query pending actions
            pending_res = await client.get("/api/v1/ai/agent/pending-actions", headers=headers)
            assert pending_res.status_code == 200
            pending_list = pending_res.json()["pending_actions"]
            assert any(p["action_id"] == action_id for p in pending_list)

            # 3. Post hardware acknowledgment from mobile client
            ack_payload = {
                "action_id": action_id,
                "status": "CONFIRMED",
                "device_alarm_id": "hw_alarm_test_778"
            }
            ack_res = await client.post("/api/v1/ai/agent/device-action-ack", json=ack_payload, headers=headers)
            assert ack_res.status_code == 200
            ack_data = ack_res.json()
            assert ack_data["status"] == "success"
            assert ack_data["result"]["acknowledged"] is True
            assert ack_data["result"]["status"] == "DEVICE_CONFIRMED"

            # 4. Verify post-ack verification succeeds
            verified, v_details = await tool.verify(ctx, exec_res)
            assert verified is True
            assert v_details["status"] == "DEVICE_CONFIRMED"
    finally:
        await db.users.delete_one({"_id": user_oid})

