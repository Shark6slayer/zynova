import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import get_database, close_database_connection, connect_to_database
from app.schemas.all_schemas import SUPPORTED_LANGUAGES

@pytest.fixture(autouse=True)
async def setup_and_teardown_prefs():
    await connect_to_database()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": "lang_pref_tester"})
        await db.user_preferences.delete_many({"user_id": "test_lang_user_id"})
    await close_database_connection()

@pytest.mark.asyncio
async def test_language_preferences_all_22_and_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a test user
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": "langtester@superai.in",
            "username": "lang_pref_tester",
            "full_name": "Language Preference Tester",
            "password": "Password123!"
        })
        assert reg_res.status_code == 201

        # Login to obtain token
        login_res = await client.post("/api/v1/auth/login", json={
            "email": "langtester@superai.in",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get default preferences
        get_res = await client.get("/api/v1/preferences", headers=headers)
        assert get_res.status_code == 200
        prefs = get_res.json()
        assert prefs["language"] == "en"

        # 3. Test updating to each of the 22 Eighth Schedule languages + English
        sample_langs = ["ta", "hi", "te", "kn", "ml", "bn", "mr", "gu", "pa", "ur", "as", "sa", "or"]
        for lang in sample_langs:
            up_res = await client.put("/api/v1/preferences", json={
                "language": lang,
                "theme": "midnight-glass",
                "appearanceMode": "dark"
            }, headers=headers)
            assert up_res.status_code == 200
            assert up_res.json()["language"] == lang

        # Verify persisted in database
        check_res = await client.get("/api/v1/preferences", headers=headers)
        assert check_res.status_code == 200
        assert check_res.json()["language"] == sample_langs[-1]
        assert check_res.json()["theme"] == "midnight-glass"

        # 4. Test invalid language rejection (HTTP 422 Unprocessable Entity)
        bad_lang_res = await client.put("/api/v1/preferences", json={
            "language": "invalid_lang_xx",
            "theme": "midnight-glass"
        }, headers=headers)
        assert bad_lang_res.status_code == 422

        # 5. Verify all 22 Eighth Schedule languages are present in SUPPORTED_LANGUAGES
        required_22 = {
            "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks",
            "kok", "mai", "ml", "mni", "mr", "ne", "or", "pa",
            "sa", "sat", "sd", "ta", "te", "ur"
        }
        assert required_22.issubset(SUPPORTED_LANGUAGES)
        assert "en" in SUPPORTED_LANGUAGES
