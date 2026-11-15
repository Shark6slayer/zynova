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

        # Phase 12.2: Video feed, playlists, saved videos & watch history indexes
        await db.videos.create_index(
            [("visibility", 1), ("status", 1), ("moderation_status", 1), ("is_deleted", 1), ("category", 1), ("created_at", -1)],
            name="videos_feed_discovery_idx",
        )
        await db.videos.create_index(
            [("is_short", 1), ("visibility", 1), ("status", 1), ("created_at", -1)],
            name="videos_shorts_feed_idx",
        )
        await db.videos.create_index([("channel_id", 1), ("created_at", -1)], name="videos_channel_idx")

        await db.video_playlists.create_index([("owner_id", 1), ("updated_at", -1)], name="video_playlists_owner_idx")

        await db.video_saves.create_index(
            [("user_id", 1), ("source", 1), ("video_id", 1)],
            unique=True,
            name="video_saves_unique_user_item",
        )
        await db.video_saves.create_index([("user_id", 1), ("saved_at", -1)], name="video_saves_user_recent_idx")

        await db.video_watch_history.create_index(
            [("user_id", 1), ("video_id", 1)],
            unique=True,
            name="video_watch_history_unique_user_video",
        )
        await db.video_watch_history.create_index(
            [("user_id", 1), ("last_watched_at", -1)],
            name="video_watch_history_user_recent_idx",
        )

        # Instagram integration indexes
        await db.instagram_connections.create_index("user_id", unique=True, name="ig_conn_user_unique")
        await db.instagram_connections.create_index("ig_user_id", unique=True, name="ig_conn_ig_user_unique")
        await db.posts.create_index(
            [("author_id", 1), ("instagram_media_id", 1)],
            unique=True,
            sparse=True,
            name="posts_unique_author_ig_media"
        )

        logger.info("Phase 24.1 & Phase 12.2 supplemental indexes verified.")
    except Exception as exc:
        logger.error(f"Phase 24.1 index setup error: {exc}")
