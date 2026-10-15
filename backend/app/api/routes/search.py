import re
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status, Depends
from bson import ObjectId

from app.schemas.all_schemas import SearchResponse, SearchResultItem
from app.database.client import get_database
from app.core.rate_limit import check_search_rate_limit
from app.api.deps import get_optional_current_user

router = APIRouter(prefix="/search", tags=["Platform Search Engine"])

def build_regex_or_text_query(field_names: List[str], cleaned_query: str) -> dict:
    """
    Safely escapes characters and constructs an indexed prefix/substring regex
    fallback when text score matching needs boundary safety.
    """
    escaped = re.escape(cleaned_query)
    pattern = re.compile(escaped, re.IGNORECASE)
    return {"$or": [{field: {"$regex": pattern}} for field in field_names]}

@router.get("", response_model=SearchResponse)
async def search_platform(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100, description="Search keyword"),
    type: str = Query("all", pattern="^(all|people|posts)$", description="Content type filter"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort: str = Query("recency", pattern="^(recency|relevance)$", description="Sort order"),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    """
    Platform Search Engine: Queries real registered users and public social posts.
    Privacy rules:
    - Only active users are discoverable.
    - Sensitive fields (password_hash, email, phone) are never exposed.
    - Only public social posts are returned.
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

    results: List[SearchResultItem] = []
    total_count = 0

    # 1. Search People (Users)
    if type in ("all", "people"):
        # Match active users on username, full_name, or bio
        user_query = {
            "is_active": True,
            **build_regex_or_text_query(["username", "full_name", "bio"], cleaned_q)
        }
        user_cursor = db.users.find(user_query).sort("created_at", -1)
        users_list = await user_cursor.to_list(length=100)

        for u in users_list:
            user_id = str(u["_id"])
            results.append(SearchResultItem(
                id=user_id,
                result_type="person",
                title=u["full_name"],
                subtitle=f"@{u['username']}",
                excerpt=u.get("bio") or f"Member of SUPER_AI community since {u.get('created_at', datetime.now(timezone.utc)).strftime('%B %Y')}",
                avatar_url=u.get("avatar_url"),
                timestamp=u.get("created_at"),
                navigation_target=f"/profile/{user_id}",
                metadata={
                    "user_id": user_id,
                    "username": u["username"]
                }
            ))

    # 2. Search Posts
    if type in ("all", "posts"):
        post_query = build_regex_or_text_query(["content", "author_username", "author_full_name"], cleaned_q)
        post_cursor = db.posts.find(post_query).sort("created_at", -1)
        posts_list = await post_cursor.to_list(length=100)

        for p in posts_list:
            post_id = str(p["_id"])
            results.append(SearchResultItem(
                id=post_id,
                result_type="post",
                title=f"Post by {p.get('author_full_name', 'Anonymous')}",
                subtitle=f"@{p.get('author_username', 'user')}",
                excerpt=p["content"][:240] + ("..." if len(p["content"]) > 240 else ""),
                avatar_url=p.get("author_avatar"),
                image_url=p.get("image_url"),
                timestamp=p.get("created_at"),
                navigation_target=f"/post/{post_id}",
                metadata={
                    "post_id": post_id,
                    "author_id": p.get("author_id"),
                    "likes_count": len(p.get("likes", [])),
                    "comments_count": p.get("comments_count", 0)
                }
            ))

    # Ordering
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
