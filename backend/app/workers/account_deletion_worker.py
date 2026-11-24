import asyncio
import logging
import signal
from datetime import datetime, timezone
from app.core.config import settings
from app.database.client import connect_to_database, close_database_connection, get_database
from app.services.account_deletion_service import AccountDeletionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("super_ai.deletion_worker")

async def run_deletion_sweep() -> int:
    """
    Selects eligible accounts for permanent cascading deletion:
    - account_status = 'pending_deletion'
    - permanent_deletion_at <= now
    Returns count of processed accounts.
    """
    db = get_database()
    if db is None:
        logger.warning("Database unavailable during deletion sweep.")
        return 0

    now = datetime.now(timezone.utc)
    # Query scheduled jobs whose permanent_deletion_at has elapsed
    cursor = db.deletion_jobs.find({
        "status": {"$in": ["scheduled", "retry"]},
        "permanent_deletion_at": {"$lte": now}
    }).limit(settings.ACCOUNT_DELETION_BATCH_SIZE)

    processed = 0
    async for job in cursor:
        user_id = job["user_id"]
        logger.info(f"Worker picked up deletion job for user_id: {user_id}")
        try:
            res = await AccountDeletionService.execute_cascading_deletion(user_id)
            logger.info(f"Processed deletion for user {user_id}: {res.get('status')}")
            processed += 1
        except Exception as e:
            logger.error(f"Error executing cascading deletion for user {user_id}: {e}")

    return processed

async def main():
    logger.info("Initializing SUPER_AI Permanent Account Deletion Worker...")
    await connect_to_database()

    # Check if run as a single sweep (e.g. Render Cron Job) or persistent daemon
    import sys
    if "--once" in sys.argv:
        logger.info("Running single deletion sweep...")
        count = await run_deletion_sweep()
        logger.info(f"Sweep completed. {count} accounts processed.")
        await close_database_connection()
        return

    logger.info(f"Worker daemon active. Sweep interval: {settings.ACCOUNT_DELETION_WORKER_INTERVAL_SECONDS}s")
    
    stop_event = asyncio.Event()

    def handle_stop():
        logger.info("Received termination signal, shutting down worker...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_stop)
        except (NotImplementedError, RuntimeError):
            # Windows or restricted loop environment fallback
            pass

    try:
        while not stop_event.is_set():
            try:
                count = await run_deletion_sweep()
                if count > 0:
                    logger.info(f"Processed {count} accounts for permanent deletion.")
            except Exception as e:
                logger.error(f"Unexpected error during sweep: {e}", exc_info=True)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.ACCOUNT_DELETION_WORKER_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass
    finally:
        await close_database_connection()
        logger.info("Deletion worker shutdown cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
