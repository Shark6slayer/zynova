"""
atlas_production_audit_tool.py - Standalone Secure Production Atlas Audit & Backup Tool

This script performs:
1. Strict Database Identity Verification:
   - Does NOT guess between 'zynova_db' and 'super_ai_db'.
   - Validates that the URI path specifies a non-empty database, or requires --database <name>.
2. Phase 3: Export timestamped JSON backup of products, restaurants, menu_items.
   - Saves backup to a new timestamped directory under C:\\super_ai\\backups\\atlas_production_<timestamp>
   - Validates JSON file readability, document count parity, and writes manifest.json BEFORE any deletion.
   - Records baseline counts for users, sellers, food_orders, shopping_orders.
3. Phase 4: Read-only dry run of candidate demo IDs (prod_01..06, rest_01..03, dish_01_1..03_2).
   - Provenance Check: Verifies ID matches seed format AND inspects document fields (e.g. is_seed_data, known seed names).
   - Referential Integrity Check: Checks if ANY shopping_orders or food_orders reference these IDs.
4. Phase 5: Strictly guarded deletion executed ONLY when BOTH --execute-deletion AND --confirm-approved are explicitly passed.
   - If not passed, the script exits immediately after dry-run without modifying any documents.

USAGE:
  # Step 1: Backup and Dry Run only (Safe, read-only - will never delete)
  python atlas_production_audit_tool.py --dry-run [--database <name>]

  # Step 2: Execute Deletion (Requires dual flags, only after manual review)
  python atlas_production_audit_tool.py --execute-deletion --confirm-approved [--database <name>]
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, List

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    import certifi
except ImportError:
    print("[FAIL] Missing dependencies. Run inside C:\\super_ai\\backend\\venv.")
    sys.exit(1)

# Known seed candidates
CANDIDATE_PRODUCTS = ["prod_01", "prod_02", "prod_03", "prod_04", "prod_05", "prod_06"]
CANDIDATE_RESTAURANTS = ["rest_01", "rest_02", "rest_03"]
CANDIDATE_MENU_ITEMS = [
    "dish_01_1", "dish_01_2", "dish_01_3",
    "dish_02_1", "dish_02_2",
    "dish_03_1", "dish_03_2"
]

KNOWN_SEED_RESTAURANT_NAMES = [
    "A2B - Adyar Ananda Bhavan",
    "Meghana Foods",
    "The Rameshwaram Cafe"
]

def get_connection_uri() -> str:
    # 1. First check environment variable
    uri = os.environ.get("ATLAS_MONGODB_URI")
    if uri and uri.strip():
        return uri.strip()

    # 2. If running interactively, prompt securely without echoing or printing
    if sys.stdin.isatty():
        try:
            import getpass
            print("[*] ATLAS_MONGODB_URI is not set in the environment.")
            prompt_uri = getpass.getpass("Enter Atlas Connection URI securely (input will not echo): ")
            if prompt_uri and prompt_uri.strip():
                return prompt_uri.strip()
        except Exception:
            pass

    # 3. If standard input has piped data
    if not sys.stdin.isatty():
        try:
            line = sys.stdin.readline()
            if line and line.strip():
                return line.strip()
        except Exception:
            pass

    print("[FAIL] No MongoDB Atlas connection URI provided.")
    print("Run interactively (you will be prompted securely), pipe via stdin, or set $env:ATLAS_MONGODB_URI in your private session.")
    sys.exit(1)

def resolve_target_database(uri: str, explicit_db: str = None) -> str:
    """
    Resolves the database target explicitly without guessing or silently defaulting.
    """
    if explicit_db:
        return explicit_db.strip()

    parsed = urlparse(uri)
    path_db = parsed.path.lstrip("/").split("?")[0].strip()
    if path_db:
        return path_db

    print("[FAIL] The connection URI does not specify a target database in its path.")
    print("Please either include the database name in the connection string or pass --database <name>.")
    sys.exit(1)

def serialize_doc(d: Any) -> Any:
    """Recursively serializes MongoDB BSON types (ObjectId, datetime) to JSON-compatible types."""
    if isinstance(d, dict):
        return {k: serialize_doc(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [serialize_doc(i) for i in d]
    elif hasattr(d, "__str__") and type(d).__name__ in ["ObjectId", "datetime"]:
        return str(d)
    return d

def safe_error_message(e: Exception) -> str:
    """Formats safe diagnostic error message without exposing connection strings or credentials."""
    err_type = type(e).__name__
    err_str = str(e)
    # Strip any potential user:pass@ substrings if present in driver exception
    if "@" in err_str and "://" in err_str:
        import re
        err_str = re.sub(r"://[^@]+@", "://<REDACTED>@", err_str)
    return f"{err_type}: {err_str}"

async def run_audit(uri: str, target_db_name: str, execute_deletion: bool = False, confirm_approved: bool = False):
    parsed = urlparse(uri)
    cluster_host = parsed.hostname or "unknown-cluster"
    
    # Connect with certifi CA bundle (timeout fast if unreachable)
    client = AsyncIOMotorClient(
        uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000
    )

    try:
        try:
            ping_res = await client.admin.command("ping")
            if not ping_res.get("ok"):
                print("[FAIL] MongoDB Atlas ping command did not return ok: 1.")
                return
        except Exception as e:
            print(f"[FAIL] Could not connect to MongoDB Atlas cluster: {safe_error_message(e)}")
            return

        # Verify cluster has the target database explicitly
        try:
            available_dbs = await client.list_database_names()
        except Exception as e:
            print(f"[FAIL] Could not list databases on cluster: {safe_error_message(e)}")
            return

        if target_db_name not in available_dbs:
            print(f"[FAIL] Target database '{target_db_name}' does not exist on cluster '{cluster_host}'.")
            print(f"Available databases on this cluster: {available_dbs}")
            return

        db = client[target_db_name]

        print("=================================================================")
        print("           ZYNOVA PRODUCTION ATLAS AUDIT & BACKUP")
        print("=================================================================")
        print(f"[*] Database Cluster Host : {cluster_host}")
        print(f"[*] Target Database Name  : {target_db_name} (VERIFIED ON CLUSTER)")
        print(f"[*] Timestamp (UTC)       : {datetime.now(timezone.utc).isoformat()}")
        print("=================================================================\n")

        # Step 1: Record Protected Collection Baseline Counts
        print("[1/4] Inspecting Protected Collection Baseline Counts...")
        users_count = await db.users.count_documents({})
        sellers_count = await db.sellers.count_documents({})
        food_orders_count = await db.food_orders.count_documents({})
        shopping_orders_count = await db.shopping_orders.count_documents({})
        print(f"  - users           : {users_count}")
        print(f"  - sellers         : {sellers_count}")
        print(f"  - food_orders     : {food_orders_count}")
        print(f"  - shopping_orders : {shopping_orders_count}")

        # Step 2: Timestamped Backup
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(r"C:\super_ai\backups") / f"atlas_production_{ts_str}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[2/4] Creating Timestamped Backup under '{backup_dir}'...")

        collections_to_backup = ["products", "restaurants", "menu_items"]
        backup_manifest = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "cluster_host": cluster_host,
            "database": target_db_name,
            "collections": {},
            "protected_baseline": {
                "users": users_count,
                "sellers": sellers_count,
                "food_orders": food_orders_count,
                "shopping_orders": shopping_orders_count
            }
        }

        for col in collections_to_backup:
            docs = await db[col].find({}).to_list(10000)
            serialized = [serialize_doc(d) for d in docs]
            col_file = backup_dir / f"{col}.json"
            with open(col_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            
            # Verify JSON parseability and exact document count match immediately
            try:
                with open(col_file, "r", encoding="utf-8") as vf:
                    verified_data = json.load(vf)
                assert len(verified_data) == len(docs), f"Count mismatch in {col} backup ({len(verified_data)} vs {len(docs)})!"
            except Exception as e:
                print(f"[FAIL] Backup verification failed for collection '{col}': {safe_error_message(e)}")
                return

            backup_manifest["collections"][col] = {
                "count": len(docs),
                "file": col_file.name,
                "verified": True
            }
            print(f"  - Backed up '{col}': {len(docs)} documents written and verified.")

        manifest_file = backup_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as mf:
            json.dump(backup_manifest, mf, indent=2)
        print(f"  -> Backup manifest created: {manifest_file} (Integrity Verified)")

        # Step 3: Dry-Run Audit of Candidate Demo IDs
        print("\n[3/4] Performing Read-Only Dry Run Audit on Demo Candidates...")

        # A. Products audit
        db_prods = await db.products.find({"_id": {"$in": CANDIDATE_PRODUCTS}}).to_list(100)
        print(f"\n  [Products] Found {len(db_prods)} of {len(CANDIDATE_PRODUCTS)} candidates in database:")
        valid_demo_prods = []
        for p in db_prods:
            pid = p["_id"]
            # Provenance: check seed flag or matching candidate list with no custom seller
            is_seed = p.get("is_seed_data", None)
            seller_id = p.get("seller_id", None)
            is_seed_provenance = (is_seed is True) or (pid in CANDIDATE_PRODUCTS and seller_id is None)

            # Referential check: query both shopping_orders.items.product_id and shopping_orders.items.id
            ref_orders = await db.shopping_orders.find({
                "$or": [
                    {"items.product_id": pid},
                    {"items.id": pid}
                ]
            }).to_list(10)

            print(f"    * ID: {pid:<10} | Name: {p.get('name')[:32]:<32} | seed_prov={is_seed_provenance} | Order refs: {len(ref_orders)}")
            if is_seed_provenance and len(ref_orders) == 0:
                valid_demo_prods.append(pid)
            else:
                print(f"      [PRESERVE] Skipping product {pid}: seed_prov={is_seed_provenance}, order_refs={len(ref_orders)}")

        # B. Restaurants audit
        db_rests = await db.restaurants.find({"_id": {"$in": CANDIDATE_RESTAURANTS}}).to_list(100)
        print(f"\n  [Restaurants] Found {len(db_rests)} of {len(CANDIDATE_RESTAURANTS)} candidates in database:")
        valid_demo_rests = []
        for r in db_rests:
            rid = r["_id"]
            r_name = r.get("name", "")
            is_seed_provenance = (r_name in KNOWN_SEED_RESTAURANT_NAMES) or (r.get("is_seed_data") is True)

            ref_orders = await db.food_orders.find({"restaurant_id": rid}).to_list(10)
            print(f"    * ID: {rid:<10} | Name: {r_name[:32]:<32} | seed_prov={is_seed_provenance} | Order refs: {len(ref_orders)}")
            if is_seed_provenance and len(ref_orders) == 0:
                valid_demo_rests.append(rid)
            else:
                print(f"      [PRESERVE] Skipping restaurant {rid}: seed_prov={is_seed_provenance}, order_refs={len(ref_orders)}")

        # C. Menu Items audit
        db_items = await db.menu_items.find({"_id": {"$in": CANDIDATE_MENU_ITEMS}}).to_list(100)
        print(f"\n  [Menu Items] Found {len(db_items)} of {len(CANDIDATE_MENU_ITEMS)} candidates in database:")
        valid_demo_items = []
        for m in db_items:
            mid = m["_id"]
            m_rest = m.get("restaurant_id")
            
            # Referential check: query food_orders for item reference
            ref_orders = await db.food_orders.find({
                "$or": [
                    {"items.item_id": mid},
                    {"items.id": mid}
                ]
            }).to_list(10)

            is_child_of_candidate = m_rest in valid_demo_rests
            print(f"    * ID: {mid:<12} | Parent: {m_rest:<10} | Name: {m.get('name')[:28]:<28} | Order refs: {len(ref_orders)}")
            if is_child_of_candidate and len(ref_orders) == 0:
                valid_demo_items.append(mid)
            else:
                print(f"      [PRESERVE] Skipping menu item {mid}: parent_valid={is_child_of_candidate}, order_refs={len(ref_orders)}")

        # User-created Catalog Verification
        all_rests = await db.restaurants.find({}).to_list(100)
        user_created_rests = [r["_id"] for r in all_rests if r["_id"] not in CANDIDATE_RESTAURANTS]
        all_items = await db.menu_items.find({}).to_list(100)
        user_created_items = [i["_id"] for i in all_items if i["_id"] not in CANDIDATE_MENU_ITEMS]

        print("\n  [User-Created Catalog Safety Check]")
        print(f"    * Preserved user-created restaurants: {len(user_created_rests)} ({user_created_rests})")
        print(f"    * Preserved user-created menu items : {len(user_created_items)} ({user_created_items})")

        # Step 4: Deletion (Strictly Guarded with dual flags)
        print("\n[4/4] Deletion Gate Status:")
        if not (execute_deletion and confirm_approved):
            print("  -> DRY RUN COMPLETE. No documents were deleted or modified.")
            print(f"  -> Validated Candidate Deletion Manifest:")
            print(f"       * Products  : {len(valid_demo_prods)} of {len(CANDIDATE_PRODUCTS)} proposed ({valid_demo_prods})")
            print(f"       * Restaurants: {len(valid_demo_rests)} of {len(CANDIDATE_RESTAURANTS)} proposed ({valid_demo_rests})")
            print(f"       * Menu Items : {len(valid_demo_items)} of {len(CANDIDATE_MENU_ITEMS)} proposed ({valid_demo_items})")
            print("\n  -> To execute deletion, review this dry-run manifest, and re-run with:")
            print("       python atlas_production_audit_tool.py --execute-deletion --confirm-approved\n")
            return

        print("  -> DUAL CONFIRMATION RECEIVED. EXECUTING APPROVED DELETIONS...")
        
        del_p = await db.products.delete_many({"_id": {"$in": valid_demo_prods}})
        print(f"     Deleted products: {del_p.deleted_count}")

        del_m = await db.menu_items.delete_many({"_id": {"$in": valid_demo_items}})
        print(f"     Deleted menu items: {del_m.deleted_count}")

        del_r = await db.restaurants.delete_many({"_id": {"$in": valid_demo_rests}})
        print(f"     Deleted restaurants: {del_r.deleted_count}")

        # Post-deletion verification
        post_prods = await db.products.count_documents({"_id": {"$in": valid_demo_prods}})
        post_rests = await db.restaurants.count_documents({"_id": {"$in": valid_demo_rests}})
        post_items = await db.menu_items.count_documents({"_id": {"$in": valid_demo_items}})
        assert post_prods == 0 and post_rests == 0 and post_items == 0, "Error: Some candidate records remain!"

        # Verify protected collections unchanged
        assert await db.users.count_documents({}) == users_count, "Integrity failure: Users count changed!"
        assert await db.sellers.count_documents({}) == sellers_count, "Integrity failure: Sellers count changed!"
        assert await db.food_orders.count_documents({}) == food_orders_count, "Integrity failure: Food orders changed!"
        assert await db.shopping_orders.count_documents({}) == shopping_orders_count, "Integrity failure: Shopping orders changed!"

        print("\n[SUCCESS] Production Deletion and Referential Integrity Confirmed.")
    finally:
        client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zynova Production Atlas Audit & Cleanup Tool")
    parser.add_argument("--dry-run", action="store_true", help="Perform backup and read-only dry-run audit (Default).")
    parser.add_argument("--execute-deletion", action="store_true", help="Enable deletion phase.")
    parser.add_argument("--confirm-approved", action="store_true", help="Explicit confirmation required to execute deletion.")
    parser.add_argument("--database", type=str, default=None, help="Explicit target database name (e.g. zynova_db).")

    args = parser.parse_args()
    
    uri = get_connection_uri()
    target_db = resolve_target_database(uri, explicit_db=args.database)
    
    asyncio.run(run_audit(
        uri=uri,
        target_db_name=target_db,
        execute_deletion=args.execute_deletion,
        confirm_approved=args.confirm_approved
    ))
