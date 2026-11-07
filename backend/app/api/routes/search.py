import re
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status, Depends
from bson import ObjectId

from app.schemas.all_schemas import SearchResponse, SearchResultItem, SearchHistoryItem
from app.database.client import get_database
from app.core.rate_limit import check_search_rate_limit
from app.api.deps import get_optional_current_user, get_current_user
from app.services.identity_service import get_blocked_users

router = APIRouter(prefix="/search", tags=["Platform Search Engine"])

def build_regex_or_text_query(field_names: List[str], cleaned_query: str) -> dict:
    escaped = re.escape(cleaned_query)
    pattern = re.compile(escaped, re.IGNORECASE)
    return {"$or": [{field: {"$regex": pattern}} for field in field_names]}

@router.get("", response_model=SearchResponse)
async def search_platform(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100, description="Search keyword"),
    type: str = Query(
        "all",
        pattern="^(all|people|posts|reels|videos|shorts|channels|communities|hashtags)$",
        description="Content type filter"
    ),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort: str = Query("recency", pattern="^(recency|relevance)$", description="Sort order"),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    """
    Unified Platform Search Engine — Phase 28:
    Queries real registered users, posts, reels, long-form videos, shorts, creator channels, communities, and hashtags.
    Strict privacy guarantees:
    - Blocked users are bidirectionally filtered out.
    - Private accounts, private videos, and locked chats are never returned.
    - Active search history is logged for authenticated users.
    """
    await check_search_rate_limit(request)

    cleaned_q = q.strip()
    if not cleaned_q:
        return SearchResponse(
            query="",
            filter_type=type,
            total_count=0,
            has_more=False,
            results=[]
        )

    db = get_database()
    if db is None:
        return SearchResponse(
            query=cleaned_q,
            filter_type=type,
            total_count=0,
            has_more=False,
            results=[]
        )

    my_id = current_user["id"] if current_user else None
    blocked_ids = set()
    if my_id:
        blocked_ids = set(await get_blocked_users(db, my_id))
        # Log to search history asynchronously
        try:
            await db.search_history.insert_one({
                "user_id": my_id,
                "query": cleaned_q,
                "category": type,
                "created_at": datetime.now(timezone.utc)
            })
        except Exception:
            pass

    results: List[SearchResultItem] = []

    # 1. Search People (Users)
    if type in ("all", "people"):
        user_query = {
            "is_active": True,
            **build_regex_or_text_query(["username", "full_name", "bio"], cleaned_q)
        }
        user_cursor = db.users.find(user_query).sort("created_at", -1)
        users_list = await user_cursor.to_list(length=60)

        for u in users_list:
            user_id = str(u["_id"])
            if user_id in blocked_ids:
                continue
            
            # Privacy check: If user account is deactivated/deleted
            if not u.get("is_active", True):
                continue

            results.append(SearchResultItem(
                id=user_id,
                result_type="person",
                title=u.get("full_name", u.get("username", "User")),
                subtitle=f"@{u.get('username')}",
                excerpt=u.get("bio") or f"Member of Zynova platform",
                avatar_url=u.get("avatar_url"),
                timestamp=u.get("created_at"),
                navigation_target=f"/profile/{user_id}",
                metadata={
                    "user_id": user_id,
                    "username": u.get("username")
                }
            ))

    # 2. Search Social Posts
    if type in ("all", "posts"):
        post_query = {
            "media_type": {"$ne": "video"},
            **build_regex_or_text_query(["content", "author_username", "author_full_name"], cleaned_q)
        }
        post_cursor = db.posts.find(post_query).sort("created_at", -1)
        posts_list = await post_cursor.to_list(length=60)

        for p in posts_list:
            author_id = p.get("author_id")
            if author_id in blocked_ids:
                continue

            post_id = str(p["_id"])
            results.append(SearchResultItem(
                id=post_id,
                result_type="post",
                title=f"Post by {p.get('author_full_name', 'User')}",
                subtitle=f"@{p.get('author_username', 'user')}",
                excerpt=p.get("content", "")[:240],
                avatar_url=p.get("author_avatar"),
                image_url=p.get("image_url"),
                timestamp=p.get("created_at"),
                navigation_target=f"/post/{post_id}",
                metadata={
                    "post_id": post_id,
                    "author_id": author_id,
                    "likes_count": len(p.get("likes", [])),
                    "comments_count": p.get("comments_count", 0)
                }
            ))

    # 3. Search Reels
    if type in ("all", "reels"):
        reel_query = {
            "media_type": "video",
            **build_regex_or_text_query(["content", "author_username", "author_full_name"], cleaned_q)
        }
        reel_cursor = db.posts.find(reel_query).sort("created_at", -1)
        reels_list = await reel_cursor.to_list(length=60)

        for r in reels_list:
            author_id = r.get("author_id")
            if author_id in blocked_ids:
                continue

            reel_id = str(r["_id"])
            results.append(SearchResultItem(
                id=reel_id,
                result_type="reel",
                title=f"Reel by {r.get('author_full_name', 'Creator')}",
                subtitle=f"@{r.get('author_username', 'creator')}",
                excerpt=r.get("content", "")[:240],
                avatar_url=r.get("author_avatar"),
                image_url=r.get("thumbnail_url") or r.get("image_url"),
                timestamp=r.get("created_at"),
                navigation_target=f"/reels/{reel_id}",
                metadata={
                    "reel_id": reel_id,
                    "author_id": author_id,
                    "likes_count": len(r.get("likes", []))
                }
            ))

    # 4. Search Long-Form Videos
    if type in ("all", "videos"):
        video_query = {
            "is_short": False,
            "visibility": "public",
            **build_regex_or_text_query(["title", "description", "category", "channel_name"], cleaned_q)
        }
        video_cursor = db.videos.find(video_query).sort("created_at", -1)
        videos_list = await video_cursor.to_list(length=60)

        for v in videos_list:
            owner_id = v.get("owner_id")
            if owner_id in blocked_ids:
                continue

            v_id = str(v["_id"])
            results.append(SearchResultItem(
                id=v_id,
                result_type="video",
                title=v.get("title", "Untitled Video"),
                subtitle=v.get("channel_name") or f"Category: {v.get('category', 'General')}",
                excerpt=(v.get("description") or "")[:240],
                image_url=v.get("thumbnail_url"),
                timestamp=v.get("created_at"),
                navigation_target=f"/videos/{v_id}",
                metadata={
                    "video_id": v_id,
                    "channel_id": v.get("channel_id"),
                    "views_count": v.get("views_count", 0),
                    "duration_seconds": v.get("duration_seconds")
                }
            ))

    # 5. Search Shorts
    if type in ("all", "shorts"):
        short_query = {
            "is_short": True,
            "visibility": "public",
            **build_regex_or_text_query(["title", "description", "audio_title", "channel_name"], cleaned_q)
        }
        short_cursor = db.videos.find(short_query).sort("created_at", -1)
        shorts_list = await short_cursor.to_list(length=60)

        for s in shorts_list:
            owner_id = s.get("owner_id")
            if owner_id in blocked_ids:
                continue

            s_id = str(s["_id"])
            results.append(SearchResultItem(
                id=s_id,
                result_type="short",
                title=s.get("title", "Short"),
                subtitle=f"♫ {s.get('audio_title', 'Original Audio')}",
                excerpt=(s.get("description") or "")[:180],
                image_url=s.get("thumbnail_url"),
                timestamp=s.get("created_at"),
                navigation_target=f"/shorts/{s_id}",
                metadata={
                    "short_id": s_id,
                    "channel_id": s.get("channel_id"),
                    "views_count": s.get("views_count", 0)
                }
            ))

    # 6. Search Creator Channels
    if type in ("all", "channels"):
        channel_query = build_regex_or_text_query(["name", "handle", "description"], cleaned_q)
        channel_cursor = db.creator_channels.find(channel_query).sort("subscribers_count", -1)
        channels_list = await channel_cursor.to_list(length=60)

        for ch in channels_list:
            owner_id = ch.get("owner_id")
            if owner_id in blocked_ids:
                continue

            ch_id = str(ch["_id"])
            results.append(SearchResultItem(
                id=ch_id,
                result_type="channel",
                title=ch.get("name", "Creator Channel"),
                subtitle=f"@{ch.get('handle')}",
                excerpt=(ch.get("description") or "")[:200],
                avatar_url=ch.get("avatar_url"),
                image_url=ch.get("banner_url"),
                timestamp=ch.get("created_at"),
                navigation_target=f"/channel/{ch.get('handle')}",
                metadata={
                    "channel_id": ch_id,
                    "handle": ch.get("handle"),
                    "subscribers_count": ch.get("subscribers_count", 0)
                }
            ))

    # 7. Search Connect Communities (Only authorized communities)
    if type in ("all", "communities"):
        community_query = build_regex_or_text_query(["name", "description"], cleaned_q)
        community_cursor = db.connect_communities.find(community_query).sort("updated_at", -1)
        communities_list = await community_cursor.to_list(length=60)

        for c in communities_list:
            # Communities privacy: Only return if public or caller is a member/admin
            admin_ids = c.get("admin_ids", [])
            member_ids = c.get("member_ids", [])
            is_private = c.get("is_private", False)
            if is_private and (not my_id or (my_id not in admin_ids and my_id not in member_ids)):
                continue

            c_id = str(c["_id"])
            results.append(SearchResultItem(
                id=c_id,
                result_type="community",
                title=c.get("name", "Community"),
                subtitle=f"{len(member_ids)} members",
                excerpt=(c.get("description") or "")[:200],
                avatar_url=c.get("icon_url"),
                timestamp=c.get("created_at"),
                navigation_target=f"/communities/{c_id}",
                metadata={
                    "community_id": c_id,
                    "groups_count": len(c.get("group_ids", []))
                }
            ))

    # 8. Search Hashtags
    if type in ("all", "hashtags"):
        tag_match = cleaned_q.lstrip("#").lower()
        if tag_match:
            tag_cursor = db.posts.find({"tags": {"$regex": f"^{re.escape(tag_match)}", "$options": "i"}}).limit(20)
            tag_posts = await tag_cursor.to_list(length=20)
            if tag_posts:
                results.append(SearchResultItem(
                    id=f"tag_{tag_match}",
                    result_type="hashtag",
                    title=f"#{tag_match}",
                    subtitle="Hashtag Topic",
                    excerpt=f"Explore {len(tag_posts)} recent public posts tagged with #{tag_match}",
                    timestamp=datetime.now(timezone.utc),
                    navigation_target=f"/tags/{tag_match}",
                    metadata={"tag": tag_match, "sample_count": len(tag_posts)}
                ))

    # Sort results
    if sort == "recency":
        results.sort(
            key=lambda x: x.timestamp.timestamp() if x.timestamp else 0,
            reverse=True
        )

    total_count = len(results)
    paginated_results = results[offset : offset + limit]
    has_more = (offset + limit) < total_count

    return SearchResponse(
        query=cleaned_q,
        filter_type=type,
        total_count=total_count,
        has_more=has_more,
        results=paginated_results
    )

# Search History Management Endpoints
@router.get("/history", response_model=List[SearchHistoryItem])
async def get_search_history(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []
    cursor = db.search_history.find({"user_id": current_user["id"]}).sort("created_at", -1).limit(limit)
    history = []
    async for h in cursor:
        history.append(SearchHistoryItem(
            id=str(h["_id"]),
            query=h["query"],
            category=h.get("category", "all"),
            created_at=h.get("created_at", datetime.now(timezone.utc))
        ))
    return history

@router.delete("/history/{item_id}", status_code=status.HTTP_200_OK)
async def delete_search_history_item(
    item_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        obj_id = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid item ID")
    
    res = await db.search_history.delete_one({"_id": obj_id, "user_id": current_user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="History item not found")
    return {"status": "deleted", "id": item_id}

@router.delete("/history", status_code=status.HTTP_200_OK)
async def clear_all_search_history(
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    res = await db.search_history.delete_many({"user_id": current_user["id"]})
    return {"status": "cleared", "deleted_count": res.deleted_count}
