"""
Phase 24.1 supplemental database indexes.
Called from _setup_indexes() in client.py via late import to avoid modifying the
existing file's line endings.
"""
import logging
logger = logging.getLogger(__name__)


async def setup_phase24_indexes(db) -> None:
    """Creates Phase 24.1 database indexes without modifying existing collections."""
    try:
        # media_assets collection
        await db.media_assets.create_index([("uploader_id", 1), ("created_at", -1)])
        await db.media_assets.create_index([("status", 1), ("purpose", 1)])
        await db.media_assets.create_index("storage_key", unique=True, sparse=True)

        # Unique video channel handle (sparse — not every user has a channel)
        await db.users.create_index(
            [("video_channel.handle", 1)],
            unique=True,
            sparse=True,
            name="video_channel_handle_unique"
        )
        # Account status for moderation queries
        await db.users.create_index([("account_status", 1)], name="users_account_status")

        # Connect messaging collections
        await db.connect_conversations.create_index(
            [("participants", 1), ("last_message_at", -1)]
        )
        await db.connect_conversations.create_index("participants")
        await db.connect_messages.create_index(
            [("conversation_id", 1), ("created_at", -1)]
        )
        await db.connect_messages.create_index(
            [("conversation_id", 1), ("sender_id", 1)]
        )

        # Social stories TTL index (expires_at field: auto-delete after 24h)
        await db.social_stories.create_index("expires_at", expireAfterSeconds=0)
        await db.social_stories.create_index([("author_id", 1), ("created_at", -1)])

        # Content reports: unique compound to prevent duplicate reports
        await db.reports.create_index(
            [("reporter_id", 1), ("target_type", 1), ("target_id", 1)],
            unique=True,
            name="reports_unique_per_reporter_target",
        )

        logger.info("Phase 24.1 supplemental indexes verified.")
    except Exception as exc:
        logger.error(f"Phase 24.1 index setup error: {exc}")
