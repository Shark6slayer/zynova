import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    social_post_rate_limiter,
    search_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_search_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    social_post_rate_limiter.requests.clear()
    search_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": {"$in": ["search_tester_1", "search_tester_2"]}})
        await db.posts.delete_many({"author_username": {"$in": ["search_tester_1", "search_tester_2"]}})
    await close_database_connection()

@pytest.mark.asyncio
async def test_platform_search_engine_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            # Clean test artifacts
            await db.users.delete_many({"username": {"$in": ["search_tester_1", "search_tester_2"]}})
            await db.posts.delete_many({"author_username": {"$in": ["search_tester_1", "search_tester_2"]}})

        # 1. Register test users with searchable fields
        reg_payload_1 = {
            "email": "searcher1@superai.in",
            "username": "search_tester_1",
            "full_name": "Vikram Adithya Sharma",
            "password": "Password123!"
        }
        res1 = await client.post("/api/v1/auth/register", json=reg_payload_1)
        assert res1.status_code == 201

        login1 = await client.post("/api/v1/auth/login", json={"email": "searcher1@superai.in", "password": "Password123!"})
        token1 = login1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        reg_payload_2 = {
            "email": "searcher2@superai.in",
            "username": "search_tester_2",
            "full_name": "Deepa Sundar",
            "password": "Password123!"
        }
        res2 = await client.post("/api/v1/auth/register", json=reg_payload_2)
        assert res2.status_code == 201

        login2 = await client.post("/api/v1/auth/login", json={"email": "searcher2@superai.in", "password": "Password123!"})
        token2 = login2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Update bio for Vikram
        await client.patch("/api/v1/users/me", headers=headers1, json={
            "bio": "Aerospace robotics engineer researching autonomous drone delivery in Bengaluru."
        })

        # 2. Publish searchable posts
        post_payload_1 = {
            "content": "Published breakthrough benchmarks for Indic quantum algorithms on ONDC architecture."
        }
        post_res1 = await client.post("/api/v1/social/posts", headers=headers1, json=post_payload_1)
        assert post_res1.status_code == 201

        post_payload_2 = {
            "content": "Exploring agricultural supply chains and localized Tamil voice interfaces."
        }
        post_res2 = await client.post("/api/v1/social/posts", headers=headers2, json=post_payload_2)
        assert post_res2.status_code == 201

        # 3. Test Search People by Name
        search_res_name = await client.get("/api/v1/search?q=Vikram&type=people")
        assert search_res_name.status_code == 200
        data_name = search_res_name.json()
        assert data_name["total_count"] >= 1
        assert any(item["title"] == "Vikram Adithya Sharma" for item in data_name["results"])
        assert any(item["subtitle"] == "@search_tester_1" for item in data_name["results"])
        assert all(item["result_type"] == "person" for item in data_name["results"])

        # 4. Test Search People by Bio Keyword
        search_res_bio = await client.get("/api/v1/search?q=aerospace&type=people")
        assert search_res_bio.status_code == 200
        data_bio = search_res_bio.json()
        assert any(item["title"] == "Vikram Adithya Sharma" for item in data_bio["results"])

        # 5. Test Search Posts by Content Keyword
        search_res_post = await client.get("/api/v1/search?q=quantum&type=posts")
        assert search_res_post.status_code == 200
        data_post = search_res_post.json()
        assert data_post["total_count"] >= 1
        assert any("quantum" in item["excerpt"].lower() for item in data_post["results"])
        assert all(item["result_type"] == "post" for item in data_post["results"])

        # 6. Test Combined Search ("all")
        search_res_all = await client.get("/api/v1/search?q=Indic&type=all")
        assert search_res_all.status_code == 200
        data_all = search_res_all.json()
        assert data_all["total_count"] >= 1

        # 7. Test Empty & Non-matching Queries
        search_empty = await client.get("/api/v1/search?q=xyznonexistentpattern999&type=all")
        assert search_empty.status_code == 200
        assert search_empty.json()["total_count"] == 0
        assert search_empty.json()["results"] == []

        # 8. Test Pagination (limit & offset)
        search_paged = await client.get("/api/v1/search?q=search_tester&type=all&limit=1&offset=0")
        assert search_paged.status_code == 200
        assert len(search_paged.json()["results"]) <= 1
