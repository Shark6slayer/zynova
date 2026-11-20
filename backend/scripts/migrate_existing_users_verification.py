"""
Database Migration: Grandfather and migrate existing accounts to verified status.
Ensures zero disruption for existing registered users who signed up before email verification was enforced.
"""

import asyncio
from datetime import datetime, timezone
from app.database.client import connect_to_database, close_database_connection, get_database

async def migrate_users():
    await connect_to_database()
    db = get_database()
    if db is None:
        print("ERROR: Database connection failed.")
        return

    # Count accounts needing migration
    query = {"$or": [{"is_verified": None}, {"is_verified": {"$exists": False}}]}
    count = await db.users.count_documents(query)
    print(f"Found {count} existing users without explicit verification status.")

    if count > 0:
        result = await db.users.update_many(
            query,
            {"$set": {
                "is_verified": True,
                "verified_at": datetime.now(timezone.utc),
                "migration_note": "Legacy user grandfathered as verified"
            }}
        )
        print(f"Successfully migrated {result.modified_count} user accounts.")
    else:
        print("No user accounts require migration.")

    await close_database_connection()

if __name__ == "__main__":
    asyncio.run(migrate_users())
