"""
ZENOVA Synthetic Staging Data Cleanup Script
Phase 16 - Isolated Testing Environment
Deletes ONLY records created with synth_ prefix / is_synthetic: True / synthetic ObjectIds.
Never touches real customer or production data.
"""
from bson import ObjectId
import pymongo

def cleanup():
    client = pymongo.MongoClient('mongodb://127.0.0.1:27017')
    db = client['super_ai_db']

    synthetic_object_ids = [
        ObjectId("6600000000000000000000a1"),
        ObjectId("6600000000000000000000b2"),
        ObjectId("6600000000000000000000c3")
    ]
    synthetic_str_ids = [str(x) for x in synthetic_object_ids]

    collections = [
        'users', 'restaurants', 'menu_items', 'products',
        'chat_rooms', 'chat_messages', 'food_orders', 'orders',
        'notifications', 'ledger_transactions', 'ai_conversations',
        'bank_accounts', 'payment_transactions'
    ]

    total_deleted = 0
    for col in collections:
        res = db[col].delete_many({
            '$or': [
                {'_id': {'$regex': '^synth_'}},
                {'_id': {'$in': synthetic_object_ids}},
                {'_id': {'$in': synthetic_str_ids}},
                {'is_synthetic': True},
                {'email': {'$in': ['synth_user_a@zenova.staging', 'synth_user_b@zenova.staging']}}
            ]
        })
        if res.deleted_count > 0:
            print(f'Deleted {res.deleted_count} synthetic docs from {col}')
            total_deleted += res.deleted_count

    print(f'CLEANUP COMPLETE: {total_deleted} total synthetic records removed.')

if __name__ == '__main__':
    cleanup()
