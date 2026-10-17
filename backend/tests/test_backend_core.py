import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import get_password_hash, verify_password, create_access_token, decode_token

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data

@pytest.mark.asyncio
async def test_version_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert data["sovereign_framework"] == "Indic-FastAPI-v2"

@pytest.mark.asyncio
async def test_readiness_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/ready")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "database" in data
    assert "status" in data
    if response.status_code == 200:
        assert data["status"] == "ready"
        assert data["database"] == "connected"
    else:
        assert data["status"] == "not_ready"
        assert data["database"] in ["unavailable", "error"]

@pytest.mark.asyncio
async def test_readiness_fails_503_when_db_offline(monkeypatch):
    from app.database import client
    # Simulate DB disconnection
    original_db = client.db_manager.db
    original_client = client.db_manager.client
    try:
        client.db_manager.db = None
        client.db_manager.client = None
        # Mock connect_to_database so it fails
        async def fail_connect():
            raise ConnectionError("Simulated Atlas TLS Handshake Error")
        monkeypatch.setattr(client, "connect_to_database", fail_connect)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "unavailable"
    finally:
        client.db_manager.db = original_db
        client.db_manager.client = original_client

def test_password_hashing():
    raw_pass = "SovereignPass2026!"
    hashed = get_password_hash(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPass123", hashed) is False

def test_jwt_token_creation_and_verification():
    payload = {"sub": "usr_9988", "email": "test@superai.in"}
    token = create_access_token(payload)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "usr_9988"
    assert decoded["email"] == "test@superai.in"
    assert decoded["type"] == "access"

@pytest.mark.asyncio
async def test_unauthorized_access():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/me")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_cors_preflight_production_origin():
    """Verifies that CORS preflight from https://zynova.intellidev.in succeeds with correct headers."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.options(
            "/api/v1/social/feed",
            headers={
                "Origin": "https://zynova.intellidev.in",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type"
            }
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://zynova.intellidev.in"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "GET" in response.headers.get("access-control-allow-methods", "")

@pytest.mark.asyncio
async def test_cors_simple_request_production_origin():
    """Verifies that simple GET request from https://zynova.intellidev.in receives CORS headers."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/health",
            headers={"Origin": "https://zynova.intellidev.in"}
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://zynova.intellidev.in"
    assert response.headers.get("access-control-allow-credentials") == "true"

@pytest.mark.asyncio
async def test_production_startup_skips_demo_seeding(monkeypatch):
    """Verifies that in production environment without explicit opt-in, catalog seeding is skipped."""
    from app.core.config import settings
    from app.database import client
    
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_DEMO_SEEDING", False)
    
    # Spy or call directly to verify early return
    # If seeding ran, it would query the database
    called = []
    class DummyDB:
        def __getattr__(self, name):
            called.append(name)
            raise AssertionError(f"Database accessed during production seed check: {name}")

    original_db = client.db_manager.db
    try:
        client.db_manager.db = DummyDB()
        await client._seed_food_catalog()
        await client._seed_shopping_catalog()
        assert len(called) == 0, "Seeding attempted database operations despite production environment!"
    finally:
        client.db_manager.db = original_db
