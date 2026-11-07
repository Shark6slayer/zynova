from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
from bson import ObjectId
from app.schemas.all_schemas import UserProfileResponse, UserUpdate, AccountDeleteRequest
from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.security import verify_password
from app.core.token_revocation import revoke_all_user_sessions

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    return UserProfileResponse(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        avatar_url=current_user.get("avatar_url"),
        bio=current_user.get("bio"),
        created_at=current_user.get("created_at", datetime.now(timezone.utc)),
        is_active=current_user.get("is_active", True)
    )

@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    update_in: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    update_fields = {}
    if update_in.full_name is not None:
        update_fields["full_name"] = update_in.full_name.strip()
    if update_in.avatar_url is not None:
        update_fields["avatar_url"] = update_in.avatar_url.strip()
    if update_in.bio is not None:
        update_fields["bio"] = update_in.bio.strip()

    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await db.users.update_one(
            {"_id": ObjectId(current_user["id"])},
            {"$set": update_fields}
        )
        current_user.update(update_fields)

    return UserProfileResponse(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        avatar_url=current_user.get("avatar_url"),
        bio=current_user.get("bio"),
        created_at=current_user.get("created_at", datetime.now(timezone.utc)),
        is_active=True
    )

@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    req: AccountDeleteRequest,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # Verify password before irreversible deletion
    user = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password. Account deletion aborted."
        )

    user_id = current_user["id"]

    # Explicit Cascade Deletion Policy (Phase 28 Multi-Platform Cascade):
    # 1. Revoke all active sessions and refresh tokens
    await revoke_all_user_sessions(user_id, reason="account_deleted")
    await db.refresh_tokens.delete_many({"user_id": user_id})
    await db.device_sessions.delete_many({"user_id": user_id})
    # 2. Delete user preferences and notification preferences
    await db.user_preferences.delete_many({"user_id": user_id})
    await db.notification_preferences.delete_many({"user_id": user_id})
    await db.search_history.delete_many({"user_id": user_id})
    # 3. Clean up Social posts, comments, follows, bookmarks
    await db.posts.delete_many({"author_id": user_id})
    await db.post_comments.delete_many({"author_id": user_id})
    await db.social_follows.delete_many({"$or": [{"follower_id": user_id}, {"following_id": user_id}]})
    await db.post_bookmarks.delete_many({"user_id": user_id})
    # 4. Clean up Connect messages, status, device keys
    await db.connect_messages.delete_many({"sender_id": user_id})
    await db.connect_status.delete_many({"user_id": user_id})
    # 5. Clean up Video creator channels, videos, watch progress
    await db.creator_channels.delete_many({"owner_id": user_id})
    await db.videos.delete_many({"owner_id": user_id})
    await db.watch_progress.delete_many({"user_id": user_id})
    # 6. Delete user AI conversations and messages
    await db.conversations.delete_many({"user_id": user_id})
    # 7. Delete user notifications
    await db.notifications.delete_many({"user_id": user_id})
    # 8. Delete primary user account record
    await db.users.delete_one({"_id": ObjectId(user_id)})

    return {
        "status": "deleted",
        "detail": "Account and all associated personal data have been completely deleted according to DPDP policy."
    }

@router.post("/me/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_my_account(
    req: AccountDeleteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Temporary account deactivation:
    - Verifies password.
    - Sets is_active = False across unified identity.
    - Revokes active sessions.
    - Hides profile from global search and discovery feeds.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    user = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect password. Deactivation aborted.")

    user_id = current_user["id"]
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc)}})
    await revoke_all_user_sessions(user_id, reason="account_deactivated")
    await db.refresh_tokens.delete_many({"user_id": user_id})

    return {"status": "deactivated", "detail": "Account deactivated. You can reactivate anytime by logging in."}

