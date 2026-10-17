import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from app.main import app
from app.core.security import create_access_token
from app.database.client import connect_to_database, close_database_connection, get_database

@pytest.fixture(autouse=True)
async def init_security_test_db():
    await connect_to_database()
    yield
    await close_database_connection()

@pytest.mark.asyncio
async def test_security_headers_present():
    """Verify SEC-03: Ensure all standard HTTP security headers are set on responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "geolocation=()" in response.headers.get("Permissions-Policy", "")
        assert response.headers.get("X-XSS-Protection") == "0"

@pytest.mark.asyncio
async def test_deactivated_user_token_rejected():
    """Verify SEC-02: Inactive/deactivated users cannot make authenticated calls."""
    db = get_database()
    if db is None:
        pytest.skip("MongoDB database unavailable for live auth test")

    deactivated_user_id = str(ObjectId())
    await db.users.insert_one({
        "_id": ObjectId(deactivated_user_id),
        "email": f"deactivated_{deactivated_user_id[:6]}@example.com",
        "username": f"deact_{deactivated_user_id[:6]}",
        "full_name": "Deactivated User",
        "is_active": False,
        "is_verified": True
    })

    try:
        token = create_access_token(data={"sub": deactivated_user_id})
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/auth/me", headers=headers)
            assert res.status_code == 403
            assert "deactivated" in res.json().get("detail", "").lower()
    finally:
        await db.users.delete_one({"_id": ObjectId(deactivated_user_id)})

@pytest.mark.asyncio
async def test_private_video_streaming_authorization():
    """Verify SEC-01: Unauthenticated and unauthorized users cannot stream private videos."""
    db = get_database()
    if db is None:
        pytest.skip("MongoDB database unavailable for video streaming test")

    owner_id = str(ObjectId())
    stranger_id = str(ObjectId())
    video_id = str(ObjectId())

    await db.videos.insert_one({
        "_id": ObjectId(video_id),
        "owner_id": owner_id,
        "owner_username": "legit_creator",
        "owner_full_name": "Legit Creator",
        "title": "Confidential Internal Video",
        "storage_key": "nonexistent_fake_key.mp4",
        "mime_type": "video/mp4",
        "file_size_bytes": 1024,
        "visibility": "private",
        "status": "ready"
    })

    await db.users.insert_one({
        "_id": ObjectId(stranger_id),
        "email": f"stranger_{stranger_id[:6]}@example.com",
        "username": f"stranger_{stranger_id[:6]}",
        "full_name": "Stranger User",
        "is_active": True
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Unauthenticated request to private video stream must be 403 Forbidden
            unauth_res = await ac.get(f"/api/v1/videos/{video_id}/stream")
            assert unauth_res.status_code == 403
            assert "private" in unauth_res.json().get("detail", "").lower()

            # 2. Unauthorized third-party user request must be 403 Forbidden
            stranger_token = create_access_token(data={"sub": stranger_id})
            stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

            auth_stranger_res = await ac.get(f"/api/v1/videos/{video_id}/stream", headers=stranger_headers)
            assert auth_stranger_res.status_code == 403
            assert "private" in auth_stranger_res.json().get("detail", "").lower()
    finally:
        await db.videos.delete_one({"_id": ObjectId(video_id)})
        await db.users.delete_one({"_id": ObjectId(stranger_id)})

@pytest.mark.asyncio
async def test_order_customer_boundary_isolation():
    """Verify BOLA protection: Users cannot view orders belonging to other customers."""
    db = get_database()
    if db is None:
        pytest.skip("MongoDB database unavailable for order isolation test")

    user_a = str(ObjectId())
    user_b = str(ObjectId())
    order_id = "test_order_boundary_999"

    # Create shopping order belonging to user_a
    await db.shopping_orders.insert_one({
        "_id": order_id,
        "customer_id": user_a,
        "customer_name": "Customer A",
        "items": [],
        "total_amount_paise": 50000,
        "currency": "INR",
        "status": "pending",
        "payment_status": "pending"
    })

    await db.users.insert_many([
        {"_id": ObjectId(user_a), "email": f"usera_{user_a[:6]}@test.com", "username": f"user_a_{user_a[:6]}", "full_name": "User A", "is_active": True},
        {"_id": ObjectId(user_b), "email": f"userb_{user_b[:6]}@test.com", "username": f"user_b_{user_b[:6]}", "full_name": "User B", "is_active": True}
    ])

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            token_b = create_access_token(data={"sub": user_b})
            headers_b = {"Authorization": f"Bearer {token_b}"}

            res = await ac.get(f"/api/v1/shopping/orders/{order_id}", headers=headers_b)
            # Expect 403 Forbidden or 404 Not Found to prevent unauthorized disclosure
            assert res.status_code in [403, 404]
    finally:
        await db.shopping_orders.delete_one({"_id": order_id})
        await db.users.delete_one({"_id": ObjectId(user_a)})
        await db.users.delete_one({"_id": ObjectId(user_b)})
