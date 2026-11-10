"""
Sovereign YouTube Data API v3 Proxy Service (Phase 12.2).
Provides:
- Cursor-based search pagination via `pageToken` (`search.list`)
- Single-batch video metadata enrichment (`videos.list`) for duration, viewCount, embeddability & categoryId
- Official region-based category discovery (`videoCategories.list`)
- Video status & embeddability verification
- Multi-tier quota protection: Redis shared TTL cache + bounded in-memory TTL fallback

Security & Compliance:
- API key read strictly from `settings.YOUTUBE_API_KEY`; never logged or sent to clients.
- Never fabricates view counts, durations, categories, or pagination tokens.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.rate_limit import get_redis_client

logger = logging.getLogger("zynova.youtube")

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
PAGE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
REGION_CODE_RE = re.compile(r"^[A-Za-z]{2}$")
ISO_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")

SEARCH_CACHE_TTL = 600        # 10 min
METADATA_CACHE_TTL = 900      # 15 min
CATEGORIES_CACHE_TTL = 86400  # 24 hr
MAX_LOCAL_CACHE = 256

# Bounded local fallback cache: key -> (expires_at, payload_dict)
_local_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def parse_iso8601_duration(iso_dur: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """
    Parses ISO-8601 duration (e.g. PT1H2M30S) into (display_str, total_seconds).
    Returns (None, None) for live streams ('P0D') or missing/invalid durations.
    """
    if not iso_dur or not isinstance(iso_dur, str):
        return None, None
    m = ISO_DURATION_RE.match(iso_dur.strip())
    if not m:
        return None, None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    total = hours * 3600 + minutes * 60 + seconds
    if total <= 0:
        return None, None
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}", total
    return f"{minutes}:{seconds:02d}", total


def _is_quota_error(status_code: int, err_data: Dict[str, Any]) -> bool:
    if status_code == 429:
        return True
    if status_code == 403:
        err = err_data.get("error", {})
        reasons = [str(e.get("reason", "")).lower() for e in err.get("errors", []) if isinstance(e, dict)]
        msg = str(err.get("message", "")).lower()
        return any("quota" in r or "dailylimit" in r or "ratelimit" in r for r in reasons) or "quota" in msg
    return False


async def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    entry = _local_cache.get(key)
    if entry:
        exp, payload = entry
        if exp > now:
            return payload
        _local_cache.pop(key, None)

    r_client = await get_redis_client()
    if r_client is not None:
        try:
            raw = await r_client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    return None


async def _cache_set(key: str, payload: Dict[str, Any], ttl: int) -> None:
    if len(_local_cache) >= MAX_LOCAL_CACHE:
        # Evict oldest expiry
        oldest_key = min(_local_cache.items(), key=lambda kv: kv[1][0])[0]
        _local_cache.pop(oldest_key, None)
    _local_cache[key] = (time.time() + ttl, payload)

    r_client = await get_redis_client()
    if r_client is not None:
        try:
            await r_client.setex(key, ttl, json.dumps(payload))
        except Exception:
            pass


def clear_youtube_cache() -> None:
    """Clears in-memory YouTube cache (for isolated unit tests)."""
    _local_cache.clear()


async def _fetch_video_metadata_batch(
    client: httpx.AsyncClient,
    api_key: str,
    video_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    Fetches official metadata (duration, viewCount, embeddable, privacyStatus, categoryId)
    in a single batch `videos.list` request rather than 1 call per video.
    """
    if not video_ids:
        return {}

    unique_ids = list(dict.fromkeys([vid for vid in video_ids if YOUTUBE_ID_RE.match(vid)]))
    if not unique_ids:
        return {}

    result_map: Dict[str, Dict[str, Any]] = {}
    uncached_ids: List[str] = []

    for vid in unique_ids:
        cached = await _cache_get(f"yt:meta:{vid}")
        if cached is not None:
            result_map[vid] = cached
        else:
            uncached_ids.append(vid)

    if uncached_ids:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet,contentDetails,statistics,status",
                "id": ",".join(uncached_ids[:50]),
                "key": api_key,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            for v in data.get("items", []):
                vid = v.get("id")
                if not vid:
                    continue
                snippet = v.get("snippet", {})
                details = v.get("contentDetails", {})
                stats = v.get("statistics", {})
                v_status = v.get("status", {})

                dur_str, dur_sec = parse_iso8601_duration(details.get("duration"))
                raw_views = stats.get("viewCount")
                view_count: Optional[int] = None
                if raw_views is not None:
                    try:
                        view_count = int(raw_views)
                    except (TypeError, ValueError):
                        view_count = None

                meta = {
                    "embeddable": bool(v_status.get("embeddable", True)),
                    "privacyStatus": v_status.get("privacyStatus", "public"),
                    "duration": dur_str,
                    "durationSeconds": dur_sec,
                    "viewCount": view_count,
                    "categoryId": snippet.get("categoryId"),
                    "title": snippet.get("title"),
                    "channelTitle": snippet.get("channelTitle"),
                    "channelId": snippet.get("channelId"),
                }
                result_map[vid] = meta
                await _cache_set(f"yt:meta:{vid}", meta, METADATA_CACHE_TTL)

    return result_map


async def search_youtube_videos(
    q: Optional[str] = None,
    category: Optional[str] = None,
    max_results: int = 15,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        return {
            "configured": False,
            "query": q or "",
            "category": category or "All",
            "videos": [],
            "next_page_token": None,
            "prev_page_token": None,
            "has_more": False,
            "cached": False,
            "quota_exceeded": False,
            "message": "YouTube Data API key (YOUTUBE_API_KEY) not configured on backend.",
        }

    if page_token is not None:
        clean_token = page_token.strip()
        if not PAGE_TOKEN_RE.match(clean_token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid pagination pageToken format.",
            )
        page_token = clean_token

    search_query = (q or "").strip() or (
        f"{category} tech india" if category and category != "All" else "technology india"
    )
    norm_cat = category or "All"
    cache_key = f"yt:search:{norm_cat.lower()}:{search_query.lower()}:{max_results}:{page_token or ''}"

    cached = await _cache_get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    params: Dict[str, Any] = {
        "part": "snippet",
        "q": search_query,
        "type": "video",
        "videoEmbeddable": "true",
        "maxResults": max_results,
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://www.googleapis.com/youtube/v3/search", params=params)
            if resp.status_code != 200:
                err_data = (
                    resp.json()
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                err_msg = err_data.get("error", {}).get(
                    "message", f"YouTube API error HTTP {resp.status_code}"
                )
                err_reasons = [
                    str(e.get("reason", "")).lower()
                    for e in err_data.get("error", {}).get("errors", [])
                    if isinstance(e, dict)
                ]
                if resp.status_code == 400 and (
                    "pagetoken" in err_msg.lower() or "invalidpagetoken" in err_reasons
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired YouTube page token.",
                    )
                if _is_quota_error(resp.status_code, err_data):
                    return {
                        "configured": True,
                        "query": search_query,
                        "category": norm_cat,
                        "videos": [],
                        "next_page_token": None,
                        "prev_page_token": None,
                        "has_more": False,
                        "cached": False,
                        "quota_exceeded": True,
                        "message": err_msg,
                    }
                return {
                    "configured": True,
                    "query": search_query,
                    "category": norm_cat,
                    "videos": [],
                    "next_page_token": None,
                    "prev_page_token": None,
                    "has_more": False,
                    "cached": False,
                    "quota_exceeded": False,
                    "message": err_msg,
                }

            data = resp.json()
            raw_items = data.get("items", [])
            vid_ids: List[str] = []
            seen_ids = set()
            snippet_by_id: Dict[str, Dict[str, Any]] = {}

            for item in raw_items:
                vid_id = item.get("id", {}).get("videoId")
                if not vid_id or not YOUTUBE_ID_RE.match(vid_id) or vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)
                vid_ids.append(vid_id)
                snippet_by_id[vid_id] = item.get("snippet", {})

            # Batch metadata lookup (1 unit instead of N units)
            meta_map = await _fetch_video_metadata_batch(client, api_key, vid_ids)

            enriched: List[Dict[str, Any]] = []
            for vid_id in vid_ids:
                snippet = snippet_by_id[vid_id]
                meta = meta_map.get(vid_id)

                # Filter out deleted, non-public, or non-embeddable items when batch lookup returned them
                if meta is not None:
                    if not meta.get("embeddable", True) or meta.get("privacyStatus", "public") != "public":
                        continue

                thumbs = snippet.get("thumbnails", {})
                thumb_url = (
                    thumbs.get("high", {}).get("url")
                    or thumbs.get("medium", {}).get("url")
                    or thumbs.get("default", {}).get("url")
                    or ""
                )
                enriched.append({
                    "id": vid_id,
                    "title": (meta or {}).get("title") or snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "channelTitle": (meta or {}).get("channelTitle") or snippet.get("channelTitle", "YouTube Creator"),
                    "channelId": (meta or {}).get("channelId") or snippet.get("channelId"),
                    "publishedAt": snippet.get("publishedAt", ""),
                    "thumbnailUrl": thumb_url,
                    "category": category or "General",
                    "categoryId": (meta or {}).get("categoryId"),
                    "duration": (meta or {}).get("duration"),
                    "durationSeconds": (meta or {}).get("durationSeconds"),
                    "viewCount": (meta or {}).get("viewCount"),
                })

            next_tok = data.get("nextPageToken")
            prev_tok = data.get("prevPageToken")
            total_results = data.get("pageInfo", {}).get("totalResults")

            payload = {
                "configured": True,
                "query": search_query,
                "category": norm_cat,
                "videos": enriched,
                "next_page_token": next_tok,
                "prev_page_token": prev_tok,
                "has_more": bool(next_tok),
                "total_results": total_results,
                "cached": False,
                "quota_exceeded": False,
                "message": None,
            }
            await _cache_set(cache_key, payload, SEARCH_CACHE_TTL)
            return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"YouTube search proxy network failure: {type(exc).__name__}")
        return {
            "configured": True,
            "query": search_query,
            "category": norm_cat,
            "videos": [],
            "next_page_token": None,
            "prev_page_token": None,
            "has_more": False,
            "cached": False,
            "quota_exceeded": False,
            "message": "Network error contacting YouTube Data API.",
        }


async def get_youtube_categories(region_code: str = "IN") -> Dict[str, Any]:
    clean_region = region_code.strip().upper()
    if not REGION_CODE_RE.match(clean_region):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="region_code must be a 2-letter ISO country code.",
        )

    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        return {
            "configured": False,
            "region_code": clean_region,
            "categories": [],
            "cached": False,
            "quota_exceeded": False,
            "message": "YouTube Data API key (YOUTUBE_API_KEY) not configured on backend.",
        }

    cache_key = f"yt:categories:{clean_region}"
    cached = await _cache_get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videoCategories",
                params={"part": "snippet", "regionCode": clean_region, "key": api_key},
            )
            if resp.status_code != 200:
                err_data = (
                    resp.json()
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                err_msg = err_data.get("error", {}).get(
                    "message", f"YouTube API error HTTP {resp.status_code}"
                )
                return {
                    "configured": True,
                    "region_code": clean_region,
                    "categories": [],
                    "cached": False,
                    "quota_exceeded": _is_quota_error(resp.status_code, err_data),
                    "message": err_msg,
                }

            data = resp.json()
            cats = []
            for item in data.get("items", []):
                sn = item.get("snippet", {})
                if sn.get("assignable", False):
                    cats.append({
                        "id": str(item.get("id")),
                        "title": sn.get("title", ""),
                        "assignable": bool(sn.get("assignable", True)),
                    })

            payload = {
                "configured": True,
                "region_code": clean_region,
                "categories": cats,
                "cached": False,
                "quota_exceeded": False,
                "message": None,
            }
            await _cache_set(cache_key, payload, CATEGORIES_CACHE_TTL)
            return payload
    except Exception as exc:
        logger.warning(f"YouTube categories failure: {type(exc).__name__}")
        return {
            "configured": True,
            "region_code": clean_region,
            "categories": [],
            "cached": False,
            "quota_exceeded": False,
            "message": "Network error contacting YouTube Data API categories endpoint.",
        }


async def get_youtube_video_status(video_id: str) -> Dict[str, Any]:
    if not YOUTUBE_ID_RE.match(video_id.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube video ID format.",
        )

    clean_id = video_id.strip()
    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        return {
            "exists": True,
            "embeddable": True,
            "privacyStatus": "public",
            "message": "Status check bypassed: API key not configured on backend.",
        }

    cached = await _cache_get(f"yt:meta:{clean_id}")
    if cached is not None:
        return {
            "exists": True,
            "embeddable": bool(cached.get("embeddable", True)),
            "privacyStatus": cached.get("privacyStatus", "public"),
            "title": cached.get("title"),
            "channelTitle": cached.get("channelTitle"),
            "duration": cached.get("duration"),
            "viewCount": cached.get("viewCount"),
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            meta_map = await _fetch_video_metadata_batch(client, api_key, [clean_id])
            meta = meta_map.get(clean_id)
            if not meta:
                return {
                    "exists": False,
                    "embeddable": False,
                    "message": "Video not found or removed from YouTube.",
                }
            return {
                "exists": True,
                "embeddable": bool(meta.get("embeddable", True)),
                "privacyStatus": meta.get("privacyStatus", "public"),
                "title": meta.get("title"),
                "channelTitle": meta.get("channelTitle"),
                "duration": meta.get("duration"),
                "viewCount": meta.get("viewCount"),
            }
    except Exception as exc:
        logger.warning(f"YouTube status lookup failed: {type(exc).__name__}")
        return {
            "exists": False,
            "embeddable": False,
            "message": "Unable to verify video status right now.",
        }
