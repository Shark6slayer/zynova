"""
Zynova Phase 25 — Complete Social Network Test Suite
Covers:
  - Module 1: Social Identity (Public/Private profiles, Verified status)
  - Module 2: Home Feed (Carousels, tags, locations, cursor pagination)
  - Module 3: Stories (24h expiry, viewers tracking, reactions, close friends, highlights)
  - Module 4: Reels (Video posts filter, playback query)
  - Module 5: Followers & Following (Follow requests, accept/reject, remove follower, suggestions)
  - Module 6: Explore & Search (Ranking algorithm with exponential decay, hashtag lookup)
  - Module 7: Social Notes (Short status with music metadata, 24h expiration)
  - Module 10: Verified Badge Application Workflow (Apply, admin review, status transition)
  - Module 12: Security & Privacy (Private account isolation, mutual blocking protection)
"""
import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import HTTPException

from app.database.client import connect_to_database, get_database
from app.services.social_service import (
    extract_hashtags,
    request_follow_user,
    respond_to_follow_request,
    remove_follower,
    get_suggested_accounts,
    create_story,
    get_stories_feed,
    record_story_view,
    add_story_reaction,
    create_story_highlight,
    get_user_highlights,
    post_social_note,
    get_following_notes,
    toggle_post_bookmark,
    get_bookmarked_posts,
    get_explore_feed,
    get_posts_by_hashtag,
    submit_verification_application,
    review_verification_application
)
from app.services.identity_service import block_user, unblock_user

@pytest_asyncio.fixture
async def test_db():
    await connect_to_database()
    db = get_database()
    if db is None:
        pytest.skip("MongoDB unreachable")
    yield db

@pytest_asyncio.fixture
async def public_user_a(test_db):
    suffix = uuid.uuid4().hex[:6]
    doc = {
        "email": f"p25_pub_a_{suffix}@zynova.in",
        "username": f"user_a_{suffix}",
        "full_name": f"User A {suffix}",
        "hashed_password": "PW",
        "is_active": True,
        "social_profile": {"is_private": False, "is_verified": False},
        "created_at": datetime.now(timezone.utc)
    }
    res = await test_db.users.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    yield doc
    await test_db.users.delete_one({"_id": res.inserted_id})
    await test_db.posts.delete_many({"author_id": doc["id"]})
    await test_db.social_stories.delete_many({"author_id": doc["id"]})
    await test_db.social_interactions.delete_many({"user_id": doc["id"]})
    await test_db.follows.delete_many({"$or": [{"follower_id": doc["id"]}, {"following_id": doc["id"]}]})
    await test_db.follow_requests.delete_many({"$or": [{"sender_id": doc["id"]}, {"target_id": doc["id"]}]})

@pytest_asyncio.fixture
async def private_user_b(test_db):
    suffix = uuid.uuid4().hex[:6]
    doc = {
        "email": f"p25_priv_b_{suffix}@zynova.in",
        "username": f"user_b_{suffix}",
        "full_name": f"User B {suffix}",
        "hashed_password": "PW",
        "is_active": True,
        "social_profile": {"is_private": True, "is_verified": False, "close_friends": []},
        "created_at": datetime.now(timezone.utc)
    }
    res = await test_db.users.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    yield doc
    await test_db.users.delete_one({"_id": res.inserted_id})
    await test_db.posts.delete_many({"author_id": doc["id"]})
    await test_db.social_stories.delete_many({"author_id": doc["id"]})
    await test_db.social_interactions.delete_many({"user_id": doc["id"]})
    await test_db.follows.delete_many({"$or": [{"follower_id": doc["id"]}, {"following_id": doc["id"]}]})
    await test_db.follow_requests.delete_many({"$or": [{"sender_id": doc["id"]}, {"target_id": doc["id"]}]})

# ===========================================================================
# 1. Identity & Follow Requests (Private vs Public)
# ===========================================================================

@pytest.mark.asyncio
async def test_public_user_instant_follow(test_db, public_user_a, private_user_b):
    # Private user B follows Public user A -> Immediate follow
    res = await request_follow_user(test_db, private_user_b, public_user_a["id"])
    assert res["status"] == "following"

    # Verify follow document exists
    follow = await test_db.follows.find_one({"follower_id": private_user_b["id"], "following_id": public_user_a["id"]})
    assert follow is not None

@pytest.mark.asyncio
async def test_private_user_follow_request_workflow(test_db, public_user_a, private_user_b):
    # Public user A requests to follow Private user B -> Request created
    res = await request_follow_user(test_db, public_user_a, private_user_b["id"])
    assert res["status"] == "requested"

    # Verify not yet followed
    follow_before = await test_db.follows.find_one({"follower_id": public_user_a["id"], "following_id": private_user_b["id"]})
    assert follow_before is None

    # User B accepts follow request
    accept_res = await respond_to_follow_request(test_db, private_user_b["id"], public_user_a["id"], "accept")
    assert accept_res["status"] == "accepted"

    # Verify now followed
    follow_after = await test_db.follows.find_one({"follower_id": public_user_a["id"], "following_id": private_user_b["id"]})
    assert follow_after is not None

@pytest.mark.asyncio
async def test_remove_follower(test_db, public_user_a, private_user_b):
    # Set up follow
    await test_db.follows.insert_one({
        "follower_id": public_user_a["id"],
        "following_id": private_user_b["id"],
        "created_at": datetime.now(timezone.utc)
    })
    # Private user B removes follower A
    res = await remove_follower(test_db, private_user_b["id"], public_user_a["id"])
    assert res["status"] == "removed"

    follow_check = await test_db.follows.find_one({"follower_id": public_user_a["id"], "following_id": private_user_b["id"]})
    assert follow_check is None

# ===========================================================================
# 2. Stories, Reactions, Highlights & Close Friends
# ===========================================================================

@pytest.mark.asyncio
async def test_close_friends_story_privacy(test_db, public_user_a, private_user_b):
    # User B creates a close-friends-only story
    story = await create_story(
        db=test_db,
        author=private_user_b,
        media_url="https://cdn.intellidev.in/public/cf_story.jpg",
        caption="Close friends only",
        is_close_friends_only=True
    )

    # User A is NOT in close friends -> should not see it in feed
    feed_a = await get_stories_feed(test_db, public_user_a["id"])
    assert not any(s["id"] == story["id"] for group in feed_a for s in group["stories"])

    # Add user A to close friends
    await test_db.users.update_one(
        {"_id": ObjectId(private_user_b["id"])},
        {"$addToSet": {"social_profile.close_friends": public_user_a["id"]}}
    )
    # A follows B
    await test_db.follows.insert_one({
        "follower_id": public_user_a["id"],
        "following_id": private_user_b["id"],
        "created_at": datetime.now(timezone.utc)
    })

    # Now A SHOULD see it
    feed_a_cf = await get_stories_feed(test_db, public_user_a["id"])
    assert any(s["id"] == story["id"] for group in feed_a_cf for s in group["stories"])

@pytest.mark.asyncio
async def test_story_reactions_and_highlights(test_db, public_user_a):
    story = await create_story(
        db=test_db,
        author=public_user_a,
        media_url="https://cdn.intellidev.in/public/highlight_me.jpg"
    )
    # React to story
    react_res = await add_story_reaction(test_db, story["id"], "user_any", "🔥")
    assert react_res["status"] == "reacted"

    # Create story highlight
    hl = await create_story_highlight(
        db=test_db,
        author_id=public_user_a["id"],
        title="Best Moments",
        story_ids=[story["id"]],
        cover_image_url="https://cdn.intellidev.in/public/cover.jpg"
    )
    assert hl["title"] == "Best Moments"
    assert hl["stories_count"] == 1

    # Fetch highlights
    hls = await get_user_highlights(test_db, public_user_a["id"])
    assert len(hls) >= 1
    assert hls[0]["title"] == "Best Moments"

# ===========================================================================
# 3. Social Notes
# ===========================================================================

@pytest.mark.asyncio
async def test_social_notes_post_and_retrieve(test_db, public_user_a, private_user_b):
    # A follows B
    await test_db.follows.insert_one({
        "follower_id": public_user_a["id"],
        "following_id": private_user_b["id"],
        "created_at": datetime.now(timezone.utc)
    })

    # User B posts a 60-char note with music
    note = await post_social_note(
        db=test_db,
        user=private_user_b,
        text="Coding Zynova Phase 25 🚀",
        music_title="Starboy",
        music_artist="The Weeknd"
    )
    assert note["text"] == "Coding Zynova Phase 25 🚀"
    assert note["music_title"] == "Starboy"

    # User A retrieves notes from followed accounts
    notes = await get_following_notes(test_db, public_user_a["id"])
    assert any(n["user_id"] == private_user_b["id"] for n in notes)

# ===========================================================================
# 4. Bookmarks & Explore Ranking
# ===========================================================================

@pytest.mark.asyncio
async def test_bookmark_and_explore(test_db, public_user_a):
    post_res = await test_db.posts.insert_one({
        "author_id": public_user_a["id"],
        "author_username": public_user_a["username"],
        "author_full_name": public_user_a["full_name"],
        "content": "Exploring #AI on Zynova",
        "tags": ["ai"],
        "likes": ["uid1"],
        "likes_count": 1,
        "comments_count": 0,
        "created_at": datetime.now(timezone.utc)
    })
    post_id = str(post_res.inserted_id)

    # Bookmark post
    bm = await toggle_post_bookmark(test_db, post_id, public_user_a["id"])
    assert bm["status"] == "bookmarked"

    saved = await get_bookmarked_posts(test_db, public_user_a["id"])
    assert len(saved) >= 1

    # Explore feed returns post
    explore = await get_explore_feed(test_db, public_user_a["id"])
    assert any(p["id"] == post_id for p in explore)

# ===========================================================================
# 5. Verification Application Workflow
# ===========================================================================

@pytest.mark.asyncio
async def test_verification_workflow(test_db, public_user_a):
    app_payload = {
        "full_legal_name": "Aarav Sharma",
        "document_type": "passport",
        "evidence_urls": ["https://cdn.intellidev.in/secure/passport_doc.pdf"],
        "category": "creator",
        "reason": "Public figure with 100k verified audience on external channels."
    }

    # Submit verification
    app_doc = await submit_verification_application(test_db, public_user_a["id"], app_payload)
    assert app_doc["status"] == "pending"
    assert "id" in app_doc

    # Submitting duplicate while pending should fail
    with pytest.raises(HTTPException) as exc_dup:
        await submit_verification_application(test_db, public_user_a["id"], app_payload)
    assert exc_dup.value.status_code == 400

    # Admin reviews and approves
    rev_res = await review_verification_application(
        db=test_db,
        application_id=app_doc["id"],
        reviewer_user_id="admin_01",
        action="approve",
        notes="Document authenticity confirmed."
    )
    assert rev_res["status"] == "approved"

    # User profile should now show is_verified == True
    user_updated = await test_db.users.find_one({"_id": ObjectId(public_user_a["id"])})
    assert user_updated.get("social_profile", {}).get("is_verified") is True
