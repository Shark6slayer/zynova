import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from bson import ObjectId

from app.core.config import settings
from app.core.security import verify_password
from app.core.token_revocation import revoke_all_user_sessions
from app.core.rate_limit import get_redis_client
from app.core.audit_ledger import record_audit_event
from app.database.client import get_database
from app.services.email_service import EmailService
from app.core.otp_service import OTPService

logger = logging.getLogger("super_ai.account_lifecycle")

class AccountDeletionService:
    """
    Manages the 30-day account deletion lifecycle and recovery:
    - Day 0: Deletion Request (status -> pending_deletion, sessions revoked, 30d timer started)
    - Days 1-29: Recovery (status -> active, deletion job cancelled)
    - Day 30+: Cascading permanent data deletion
    """

    @classmethod
    async def request_deletion(
        cls,
        user_id: str,
        password: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes a Day 0 account deletion request:
        1. Authenticates current user password.
        2. Sets account_status = 'pending_deletion', records timestamps.
        3. Sets permanent_deletion_at = deletion_requested_at + 30 days.
        4. Revokes all active access and refresh tokens.
        5. Invalidates sessions and user-specific Redis keys.
        6. Inserts or updates a durable deletion_job record in MongoDB.
        """
        db = get_database()
        if db is None:
            raise RuntimeError("Database unavailable")

        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user or not verify_password(password, user["hashed_password"]):
            raise ValueError("Incorrect password. Deletion request rejected.")

        if user.get("account_status") == "pending_deletion":
            # Already pending deletion, return current status
            return {
                "status": "pending_deletion",
                "deletion_requested_at": user.get("deletion_requested_at"),
                "permanent_deletion_at": user.get("permanent_deletion_at"),
                "days_remaining": max(0, int((user["permanent_deletion_at"] - datetime.now(timezone.utc)).total_seconds() // 86400)),
                "message": "Account is already scheduled for permanent deletion."
            }

        now = datetime.now(timezone.utc)
        permanent_at = now + timedelta(days=settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS)

        # 1. Update user document atomically
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "account_status": "pending_deletion",
                "deletion_requested_at": now,
                "permanent_deletion_at": permanent_at,
                "deletion_reason": reason,
                "is_active": False,
                "updated_at": now
            }}
        )

        # 2. Durable deletion job record
        await db.deletion_jobs.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "email": user["email"],
                "status": "scheduled",
                "deletion_requested_at": now,
                "permanent_deletion_at": permanent_at,
                "attempts": 0,
                "last_attempt_at": None,
                "error": None,
                "updated_at": now
            }},
            upsert=True
        )

        # 3. Revoke all active sessions and refresh tokens
        await revoke_all_user_sessions(user_id, reason="account_deletion_requested")
        await db.refresh_tokens.delete_many({"user_id": user_id})
        await db.device_sessions.delete_many({"user_id": user_id})

        # 4. Invalidate Redis keys and user caches
        r_client = await get_redis_client()
        if r_client is not None:
            try:
                await r_client.delete(f"user_session:{user_id}")
                await r_client.delete(f"user_profile:{user_id}")
            except Exception as e:
                logger.warning(f"Failed to clear Redis keys for user {user_id}: {e}")

        # 5. Audit event
        await record_audit_event(
            event_type="ACCOUNT_DELETION_REQUESTED",
            raw_actor_id=user_id,
            metadata={
                "grace_period_days": settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS,
                "permanent_deletion_at": permanent_at.isoformat()
            }
        )

        days_left = max(0, int((permanent_at - now).total_seconds() // 86400))
        return {
            "status": "pending_deletion",
            "account_status": "pending_deletion",
            "deletion_requested_at": now,
            "permanent_deletion_at": permanent_at,
            "days_remaining": days_left,
            "message": f"Account scheduled for permanent deletion on {permanent_at.strftime('%Y-%m-%d %H:%M:%S UTC')}. You have {days_left} days to recover your account."
        }

    @classmethod
    async def get_deletion_status(cls, user_id: str) -> Dict[str, Any]:
        """Returns the current deletion status and remaining recovery time."""
        db = get_database()
        if db is None:
            raise RuntimeError("Database unavailable")

        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return {
                "status": "deleted",
                "account_status": "deleted",
                "can_recover": False,
                "message": "Account does not exist or has been permanently deleted."
            }

        account_status = user.get("account_status", "active" if user.get("is_active", True) else "deactivated")
        now = datetime.now(timezone.utc)

        if account_status == "pending_deletion":
            perm_at = user.get("permanent_deletion_at")
            if perm_at:
                if perm_at.tzinfo is None:
                    perm_at = perm_at.replace(tzinfo=timezone.utc)
                remaining_sec = max(0, int((perm_at - now).total_seconds()))
                remaining_days = remaining_sec // 86400
                can_recover = remaining_sec > 0
            else:
                remaining_sec = 0
                remaining_days = 0
                can_recover = False

            return {
                "status": "pending_deletion",
                "account_status": "pending_deletion",
                "deletion_requested_at": user.get("deletion_requested_at"),
                "permanent_deletion_at": perm_at,
                "days_remaining": remaining_days,
                "seconds_remaining": remaining_sec,
                "can_recover": can_recover,
                "message": f"Account deletion pending. {remaining_days} days remaining to recover."
            }

        return {
            "status": "active",
            "account_status": account_status,
            "deletion_requested_at": None,
            "permanent_deletion_at": None,
            "days_remaining": None,
            "seconds_remaining": None,
            "can_recover": False,
            "message": "Account is active and not scheduled for deletion."
        }

    @classmethod
    async def recover_account(
        cls,
        email: str,
        password: str,
        otp_code: str
    ) -> Dict[str, Any]:
        """
        Recovers an account during Days 1-29:
        1. Verifies password.
        2. Verifies cryptographic 6-digit OTP sent to verified email.
        3. Verifies account is currently in 'pending_deletion' and permanent_deletion_at > now.
        4. Atomically restores account_status = 'active', is_active = True.
        5. Cancels the scheduled deletion job.
        6. Clears deletion timestamps.
        """
        clean_email = email.lower().strip()
        db = get_database()
        if db is None:
            raise RuntimeError("Database unavailable")

        user = await db.users.find_one({"email": clean_email})
        if not user or not verify_password(password, user["hashed_password"]):
            raise ValueError("Invalid email or password.")

        user_id = str(user["_id"])

        if user.get("account_status") != "pending_deletion":
            return {
                "status": "active",
                "message": "Account is already active.",
                "email": clean_email,
                "account_status": user.get("account_status", "active"),
                "recovered_at": datetime.now(timezone.utc)
            }

        now = datetime.now(timezone.utc)
        perm_at = user.get("permanent_deletion_at")
        if perm_at:
            if perm_at.tzinfo is None:
                perm_at = perm_at.replace(tzinfo=timezone.utc)
            if perm_at <= now:
                raise ValueError("The 30-day recovery window for this account has expired and deletion has committed.")

        # Verify OTP
        otp_ok, otp_err = await OTPService.verify_email_otp(clean_email, otp_code)
        if not otp_ok:
            raise ValueError(otp_err or "Invalid or expired verification code.")

        # Atomic state restoration using MongoDB conditional update to avoid race with deletion worker
        result = await db.users.update_one(
            {
                "_id": ObjectId(user_id),
                "account_status": "pending_deletion"
            },
            {"$set": {
                "account_status": "active",
                "is_active": True,
                "updated_at": now
            }, "$unset": {
                "deletion_requested_at": "",
                "permanent_deletion_at": "",
                "deletion_reason": ""
            }}
        )

        if result.modified_count == 0:
            raise ValueError("Account recovery failed: state changed or already processed.")

        # Cancel deletion job
        await db.deletion_jobs.update_one(
            {"user_id": user_id, "status": "scheduled"},
            {"$set": {"status": "cancelled", "cancelled_at": now, "updated_at": now}}
        )

        # Audit event
        await record_audit_event(
            event_type="ACCOUNT_RECOVERY_SUCCESS",
            raw_actor_id=user_id,
            metadata={"domain": clean_email.split("@")[-1]}
        )

        return {
            "status": "recovered",
            "message": "Account recovered successfully. Full access has been restored.",
            "email": clean_email,
            "account_status": "active",
            "recovered_at": now
        }

    @classmethod
    async def execute_cascading_deletion(cls, user_id: str) -> Dict[str, Any]:
        """
        Executes permanent cascading deletion for an account after the 30-day grace period:
        - Locks the job to prevent duplicate concurrent runs.
        - Removes media objects from Cloudflare R2 / storage adapter.
        - Cascades deletion across all modules: Social, Connect, Video, Cart, Search, Notifications, Sessions.
        - Deletes primary user account record.
        - Marks deletion_job as completed.
        """
        db = get_database()
        if db is None:
            raise RuntimeError("Database unavailable")

        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            # User already deleted, mark job completed
            await db.deletion_jobs.update_one(
                {"user_id": user_id},
                {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}}
            )
            return {"status": "already_deleted", "user_id": user_id}

        # Double check status immediately before committing deletion
        if user.get("account_status") != "pending_deletion":
            logger.info(f"Skipping deletion for user {user_id}: account_status is {user.get('account_status')}")
            await db.deletion_jobs.update_one(
                {"user_id": user_id},
                {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}}
            )
            return {"status": "cancelled", "reason": "account_not_pending_deletion"}

        now = datetime.now(timezone.utc)
        perm_at = user.get("permanent_deletion_at")
        if perm_at:
            if perm_at.tzinfo is None:
                perm_at = perm_at.replace(tzinfo=timezone.utc)
            if perm_at > now:
                logger.info(f"Grace period not yet passed for user {user_id}")
                return {"status": "grace_period_active", "permanent_deletion_at": perm_at}

        # Atomically transition job to 'processing' to avoid concurrent worker conflicts
        lock_res = await db.deletion_jobs.update_one(
            {"user_id": user_id, "status": {"$in": ["scheduled", "retry"]}},
            {"$set": {"status": "processing", "last_attempt_at": now}}
        )
        if lock_res.modified_count == 0:
            logger.warning(f"Job for user {user_id} is already being processed or not eligible.")
            return {"status": "locked_or_ineligible"}

        logger.info(f"Executing permanent cascading deletion for user {user_id}...")

        try:
            # 1. External Media Cleanup (Cloudflare R2 / S3 / LocalDev)
            try:
                from app.services.media_service import get_storage_adapter
                adapter = get_storage_adapter()
                cursor = db.media_assets.find({"uploader_id": user_id, "status": {"$ne": "deleted"}})
                async for asset in cursor:
                    try:
                        await adapter.delete_file(asset["storage_key"])
                    except Exception as media_err:
                        logger.warning(f"Error removing storage key {asset.get('storage_key')}: {media_err}")
                await db.media_assets.delete_many({"uploader_id": user_id})
            except Exception as e:
                logger.warning(f"Media storage adapter cleanup warning: {e}")

            # 2. Redis Sessions & Keys
            r_client = await get_redis_client()
            if r_client is not None:
                try:
                    await r_client.delete(f"user_session:{user_id}")
                    await r_client.delete(f"user_profile:{user_id}")
                    await r_client.delete(f"otp_cooldown:{user['email']}")
                except Exception as redis_err:
                    logger.warning(f"Error purging Redis keys: {redis_err}")

            # 3. Identity and authentication records
            await revoke_all_user_sessions(user_id, reason="account_permanently_deleted")
            await db.refresh_tokens.delete_many({"user_id": user_id})
            await db.device_sessions.delete_many({"user_id": user_id})
            await db.user_preferences.delete_many({"user_id": user_id})
            await db.notification_preferences.delete_many({"user_id": user_id})
            await db.search_history.delete_many({"user_id": user_id})
            await db.email_verifications.delete_many({"email": user["email"]})

            # 4. ZenoSocial records
            await db.posts.delete_many({"author_id": user_id})
            await db.post_comments.delete_many({"author_id": user_id})
            await db.social_follows.delete_many({"$or": [{"follower_id": user_id}, {"following_id": user_id}]})
            await db.post_bookmarks.delete_many({"user_id": user_id})
            # Remove likes authored by this user from all posts
            await db.posts.update_many({"likes": user_id}, {"$pull": {"likes": user_id}})

            # 5. ZENOVA Connect records
            await db.connect_messages.delete_many({"sender_id": user_id})
            await db.connect_status.delete_many({"user_id": user_id})
            await db.chat_rooms.update_many({"participants": user_id}, {"$pull": {"participants": user_id}})
            await db.chat_messages.delete_many({"sender": user_id})

            # 6. Video & Creator records
            await db.creator_channels.delete_many({"owner_id": user_id})
            await db.videos.delete_many({"owner_id": user_id})
            await db.video_comments.delete_many({"author_id": user_id})
            await db.video_views.delete_many({"viewer_key": user_id})
            await db.watch_progress.delete_many({"user_id": user_id})

            # 7. AI Conversations & Notifications
            await db.conversations.delete_many({"user_id": user_id})
            await db.notifications.delete_many({"user_id": user_id})

            # 8. Shopping & Orders (User owned cart/history)
            await db.shopping_orders.delete_many({"customer_id": user_id})
            await db.food_orders.delete_many({"customer_id": user_id})

            # 9. Primary User Document
            await db.users.delete_one({"_id": ObjectId(user_id)})

            # 10. Mark Job Completed
            await db.deletion_jobs.update_one(
                {"user_id": user_id},
                {"$set": {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

            await record_audit_event(
                event_type="ACCOUNT_PERMANENTLY_DELETED",
                raw_actor_id=user_id,
                metadata={"action": "cascading_deletion_completed"}
            )

            logger.info(f"Cascading data deletion successfully completed for user {user_id}")
            return {"status": "completed", "user_id": user_id}

        except Exception as e:
            logger.error(f"Permanent deletion failed for user {user_id}: {e}", exc_info=True)
            await db.deletion_jobs.update_one(
                {"user_id": user_id},
                {"$set": {
                    "status": "retry",
                    "error": str(e),
                    "updated_at": datetime.now(timezone.utc)
                }, "$inc": {"attempts": 1}}
            )
            raise e
