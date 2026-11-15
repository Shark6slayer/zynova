import asyncio
import logging
from datetime import datetime, timezone, timedelta
from app.database.client import get_database
from app.core.crypto_kms import decrypt_field
from app.services.meta_instagram_service import MetaInstagramService

logger = logging.getLogger("zynova.instagram_validator")

async def validate_and_refresh_instagram_connections():
    """
    Daily token refresh/validate task:
    Inspects connections expiring within a 7-day window.
    On failure or expired token, sets status to 'needs_reconnect'.
    """
    db = get_database()
    if db is None:
        return

    now = datetime.now(timezone.utc)
    warning_threshold = now + timedelta(days=7)

    cursor = db.instagram_connections.find({
        "status": "active",
        "token_expires_at": {"$lte": warning_threshold}
    })

    async for conn in cursor:
        user_id = conn["user_id"]
        try:
            page_token = decrypt_field(conn["access_token_enc"], context=f"ig_page_token:{user_id}")
            inspection = await MetaInstagramService.inspect_token(page_token)
            if not inspection.get("is_valid", False):
                logger.warning(f"Instagram token invalid for user {user_id}. Marking needs_reconnect.")
                await db.instagram_connections.update_one(
                    {"_id": conn["_id"]},
                    {"$set": {"status": "needs_reconnect"}}
                )
            else:
                # Update last validated timestamp
                await db.instagram_connections.update_one(
                    {"_id": conn["_id"]},
                    {"$set": {"last_synced_at": now}}
                )
        except Exception as e:
            logger.error(f"Error validating token for user {user_id}: {e}")
            await db.instagram_connections.update_one(
                {"_id": conn["_id"]},
                {"$set": {"status": "needs_reconnect"}}
            )
