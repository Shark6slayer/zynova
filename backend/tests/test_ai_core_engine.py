import pytest
import uuid
from bson import ObjectId
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, get_database
from app.core.security import create_access_token

@pytest.fixture(autouse=True)
async def ai_test_db_lifecycle():
    await connect_to_database()
    yield
    db = get_database()
    if db is not None:
        await db.ai_conversations.delete_many({"user_id": {"$regex": "^test_ai_"}})

@pytest.mark.asyncio
async def test_ai_models_endpoint_unauthenticated():
    """Verify that models metadata endpoint is public and reports configured status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/ai/models")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        models = data["models"]
        assert len(models) >= 1
        mock_model = next((m for m in models if m["provider"] == "mock"), None)
        assert mock_model is not None
        assert mock_model["is_configured"] is True

@pytest.mark.asyncio
async def test_ai_conversations_requires_auth():
    """Verify conversation operations enforce authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/ai/conversations")
        assert res.status_code in [401, 403]

@pytest.mark.asyncio
async def test_ai_chat_streaming_lifecycle():
    """Verify authenticated SSE streaming inference, message persistence, and conversation isolation."""
    db = get_database()
    user_oid = ObjectId()
    user_id = str(user_oid)
    rand_suffix = uuid.uuid4().hex[:8]

    # Insert user doc into db for get_current_user dependency with unique username
    await db.users.insert_one({
        "_id": user_oid,
        "email": f"test_ai_{user_id}@example.com",
        "username": f"ai_tester_{rand_suffix}",
        "is_active": True
    })

    token = create_access_token(data={"sub": user_id, "username": f"ai_tester_{rand_suffix}"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Invoke chat stream
        payload = {
            "prompt": "Hello Zynova, testing sovereign AI engine",
            "provider": "mock",
            "model": "mock-indic-v1",
            "locale": "ta"
        }
        res = await client.post("/api/v1/ai/chat/stream", json=payload, headers=headers)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        body = res.text
        assert "data: " in body
        assert "[MockAI]" in body

        # 2. List conversations
        list_res = await client.get("/api/v1/ai/conversations", headers=headers)
        assert list_res.status_code == 200
        convs = list_res.json()["conversations"]
        assert len(convs) >= 1
        conv_id = convs[0]["id"]

        # 3. Fetch details of conversation
        detail_res = await client.get(f"/api/v1/ai/conversations/{conv_id}", headers=headers)
        assert detail_res.status_code == 200
        conv_data = detail_res.json()["conversation"]
        msgs = conv_data["messages"]
        assert len(msgs) >= 2  # user message + assistant reply
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

        # 4. Cross-user isolation check: another user cannot access this conversation
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

        # Clean up test user docs
        await db.users.delete_many({"_id": {"$in": [user_oid, other_oid]}})
