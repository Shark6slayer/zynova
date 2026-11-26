import asyncio
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
    unset_fields = {}
    if update_in.full_name is not None:
        update_fields["full_name"] = update_in.full_name.strip()
    if update_in.avatar_url is not None:
        update_fields["avatar_url"] = update_in.avatar_url.strip()
    if update_in.bio is not None:
        update_fields["bio"] = update_in.bio.strip()
    if update_in.phone_number is not None:
        new_phone = update_in.phone_number.strip()
        existing_phone = current_user.get("phone_number") or current_user.get("phone")
        if new_phone != existing_phone:
            # Store unverified input strictly in pending_phone (non-unique).
            # NEVER write unverified numbers to phone_number (prevents claiming or blocking).
            update_fields["pending_phone"] = new_phone
            # If the user previously had a verified phone and requested a change,
            # clear the active phone_number and phone using $unset, never phone_number=None,
            # and reset verification flags.
            unset_fields["phone_number"] = ""
            unset_fields["phone"] = ""
            unset_fields["phone_verified_at"] = ""
            update_fields["is_phone_verified"] = False
            update_fields["phone_verified"] = False
            update_fields["connect_activated"] = False

    if update_fields or unset_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        mongo_update = {}
        if update_fields:
            mongo_update["$set"] = update_fields
        if unset_fields:
            mongo_update["$unset"] = unset_fields

        await db.users.update_one(
            {"_id": ObjectId(current_user["id"])},
            mongo_update
        )
        current_user.update(update_fields)
        for k in unset_fields:
            current_user.pop(k, None)

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
    """
    Day 0 Account Deletion Request (30-day grace period):
    - Re-authenticates with password.
    - Transitions account to 'pending_deletion'.
    - Starts the 30-day recovery countdown.
    - Revokes active sessions and tokens.
    """
    from app.services.account_deletion_service import AccountDeletionService
    try:
        res = await AccountDeletionService.request_deletion(
            user_id=current_user["id"],
            password=req.password,
            reason="User requested deletion via /users/me"
        )
        return {
            "status": "pending_deletion",
            "account_status": "pending_deletion",
            "deletion_requested_at": res.get("deletion_requested_at"),
            "permanent_deletion_at": res.get("permanent_deletion_at"),
            "days_remaining": res.get("days_remaining"),
            "detail": res["message"]
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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
    if not user or not await asyncio.to_thread(verify_password, req.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect password. Deactivation aborted.")

    user_id = current_user["id"]
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc)}})
    await revoke_all_user_sessions(user_id, reason="account_deactivated")
    await db.refresh_tokens.delete_many({"user_id": user_id})

    return {"status": "deactivated", "detail": "Account deactivated. You can reactivate anytime by logging in."}

