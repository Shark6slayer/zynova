"""
ZENOVA Synthetic Staging Data Provisioning Script
Phase 16 - Isolated Testing Environment
Prefix: synth_
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from bson import ObjectId
import pymongo
from app.core.security import get_password_hash

def provision():
    client = pymongo.MongoClient('mongodb://127.0.0.1:27017')
    db = client['super_ai_db']
    now = datetime.now(timezone.utc)

    id_alice = ObjectId("6600000000000000000000a1")
    id_bob = ObjectId("6600000000000000000000b2")
    id_conv = ObjectId("6600000000000000000000c3")
    str_alice = str(id_alice)
    str_bob = str(id_bob)
    str_conv = str(id_conv)

    hashed_pw = get_password_hash("SyntheticPass123!")

    # 1. Users
    user_a = {
        '_id': id_alice,
        'email': 'synth_user_a@zenova.staging',
        'username': 'synth_alice',
        'full_name': 'Synthetic Alice Tester',
        'hashed_password': hashed_pw,
        'is_active': True,
        'avatar_url': 'https://api.zenova.intellidev.in/static/avatars/alice.png',
        'bio': 'Synthetic QA Account A for Sovereign Staging Verification.',
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    user_b = {
        '_id': id_bob,
        'email': 'synth_user_b@zenova.staging',
        'username': 'synth_bob',
        'full_name': 'Synthetic Bob Tester',
        'hashed_password': hashed_pw,
        'is_active': True,
        'avatar_url': 'https://api.zenova.intellidev.in/static/avatars/bob.png',
        'bio': 'Synthetic QA Account B for Sovereign Staging Verification.',
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    db.users.replace_one({'_id': user_a['_id']}, user_a, upsert=True)
    db.users.replace_one({'_id': user_b['_id']}, user_b, upsert=True)

    # 2. Restaurants
    rest_1 = {
        '_id': 'synth_rest_001',
        'name': 'Sovereign Spice Kitchen',
        'description': 'Verified synthetic test kitchen for automated QA',
        'service_area': 'Indiranagar',
        'address': '100ft Road, Indiranagar, Bengaluru',
        'cuisine': 'South Indian',
        'rating': 4.8,
        'time_mins': 20,
        'price_for_two_inr': 350,
        'is_veg': False,
        'image_url': 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c',
        'is_open': True,
        'owner_id': str_alice,
        'is_synthetic': True,
        'created_at': now
    }
    rest_2 = {
        '_id': 'synth_rest_002',
        'name': 'Green Leaf Veg Haven',
        'description': 'Pure vegetarian organic South Indian delicacies',
        'service_area': 'Indiranagar',
        'address': '12th Main, Indiranagar, Bengaluru',
        'cuisine': 'South Indian',
        'rating': 4.9,
        'time_mins': 15,
        'price_for_two_inr': 300,
        'is_veg': True,
        'image_url': 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd',
        'is_open': True,
        'owner_id': str_bob,
        'is_synthetic': True,
        'created_at': now
    }
    db.restaurants.replace_one({'_id': rest_1['_id']}, rest_1, upsert=True)
    db.restaurants.replace_one({'_id': rest_2['_id']}, rest_2, upsert=True)

    # 3. Menu Items
    item_1 = {
        '_id': 'synth_item_001',
        'restaurant_id': 'synth_rest_001',
        'name': 'Ghee Roast Dosa',
        'description': 'Crispy golden crepe roasted with pure desi ghee',
        'price_paise': 12000,
        'is_veg': True,
        'is_available': True,
        'category': 'Mains',
        'image_url': 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc',
        'is_synthetic': True
    }
    item_2 = {
        '_id': 'synth_item_002',
        'restaurant_id': 'synth_rest_001',
        'name': 'Filter Coffee',
        'description': 'Traditional Kumbakonam brass degree filter coffee',
        'price_paise': 4000,
        'is_veg': True,
        'is_available': True,
        'category': 'Beverages',
        'image_url': 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd',
        'is_synthetic': True
    }
    db.menu_items.replace_one({'_id': item_1['_id']}, item_1, upsert=True)
    db.menu_items.replace_one({'_id': item_2['_id']}, item_2, upsert=True)

    # 4. Products
    prod_1 = {
        '_id': 'synth_prod_001',
        'name': 'Zenova Pulse Wireless Earbuds',
        'brand': 'ZENOVA Audio',
        'sku': 'SYNTH-AUD-001',
        'category': 'Electronics',
        'description': 'Active noise cancellation earbuds with sovereign Bluetooth LE.',
        'price_paise': 199900,
        'mrp_paise': 399900,
        'rating': 4.7,
        'reviews_count': 128,
        'stock': 50,
        'is_available': True,
        'is_published': True,
        'is_seed_data': False,
        'images': ['https://images.unsplash.com/photo-1590658268037-6bf12165a8df'],
        'features': ['ANC 32dB', '40H Battery Life', 'IPX5 Waterproof'],
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    prod_2 = {
        '_id': 'synth_prod_002',
        'name': 'Sovereign Cotton Hoodie',
        'brand': 'ZENOVA Apparel',
        'sku': 'SYNTH-APP-002',
        'category': 'Fashion',
        'description': '100% organic combed cotton heavyweight hoodie with embroidered logo.',
        'price_paise': 89900,
        'mrp_paise': 149900,
        'rating': 4.8,
        'reviews_count': 84,
        'stock': 100,
        'is_available': True,
        'is_published': True,
        'is_seed_data': False,
        'images': ['https://images.unsplash.com/photo-1556905055-8f358a7a47b2'],
        'features': ['100% Cotton', 'Pre-shrunk Fleece', 'Oversized Fit'],
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    db.products.replace_one({'_id': prod_1['_id']}, prod_1, upsert=True)
    db.products.replace_one({'_id': prod_2['_id']}, prod_2, upsert=True)

    # 5. Bank Account for Alice
    bank_acc_1 = {
        '_id': 'synth_acc_alice_001',
        'user_id': str_alice,
        'bank_name': 'State Bank of India',
        'account_number_masked': '•••• 9012',
        'account_number': '123456789012',
        'ifsc_code': 'SBIN0001234',
        'account_type': 'savings',
        'is_default': True,
        'balance_paise': 5000000,
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    db.bank_accounts.replace_one({'_id': bank_acc_1['_id']}, bank_acc_1, upsert=True)

    # 6. Chat Room & Messages
    conv_1 = {
        '_id': id_conv,
        'type': 'direct',
        'name': 'Alice & Bob Sync',
        'participants': [str_alice, str_bob],
        'unread_counts': {str_alice: 0, str_bob: 1},
        'last_message': {
            'id': 'synth_msg_001',
            'sender_id': str_alice,
            'text': 'Hello Bob, testing sovereign chat delivery!',
            'created_at': now
        },
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    msg_1 = {
        '_id': 'synth_msg_001',
        'conversation_id': str_conv,
        'sender_id': str_alice,
        'text': 'Hello Bob, testing sovereign chat delivery!',
        'delivery_status': 'delivered',
        'read_by': [str_alice],
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    msg_2 = {
        '_id': 'synth_msg_002',
        'conversation_id': str_conv,
        'sender_id': str_bob,
        'text': 'Received Alice, end-to-end verified.',
        'delivery_status': 'read',
        'read_by': [str_alice, str_bob],
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    db.chat_rooms.replace_one({'_id': conv_1['_id']}, conv_1, upsert=True)
    db.chat_messages.replace_one({'_id': msg_1['_id']}, msg_1, upsert=True)
    db.chat_messages.replace_one({'_id': msg_2['_id']}, msg_2, upsert=True)

    # 7. Orders
    food_order_1 = {
        '_id': 'synth_order_food_001',
        'customer_id': str_alice,
        'customer_name': 'Synthetic Alice Tester',
        'customer_email': 'synth_user_a@zenova.staging',
        'restaurant_id': 'synth_rest_001',
        'restaurant_name': 'Sovereign Spice Kitchen',
        'items': [{
            'item_id': 'synth_item_001',
            'name': 'Ghee Roast Dosa',
            'quantity': 1,
            'price_paise': 12000
        }],
        'item_count': 1,
        'delivery_address': 'Indiranagar 100ft Rd, Bengaluru',
        'subtotal_paise': 12000,
        'delivery_fee_paise': 3000,
        'taxes_paise': 1000,
        'total_paise': 16000,
        'payment_method': 'cod',
        'payment_status': 'pending',
        'order_status': 'confirmed',
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    db.food_orders.replace_one({'_id': food_order_1['_id']}, food_order_1, upsert=True)

    # 8. Notifications
    notif_1 = {
        '_id': 'synth_notif_001',
        'user_id': str_alice,
        'actor_user_id': 'system',
        'category': 'Orders',
        'event_type': 'order_confirmed',
        'title': 'Food Order Confirmed',
        'desc': 'Sovereign Spice Kitchen is preparing your Ghee Roast Dosa!',
        'time': 'Just now',
        'read': False,
        'metadata': {'order_id': 'synth_order_food_001'},
        'is_synthetic': True,
        'created_at': now,
        'updated_at': now
    }
    db.notifications.replace_one({'_id': notif_1['_id']}, notif_1, upsert=True)

    print('SYNTHETIC PROVISIONING SUCCESSFUL')
    print(f'Alice ID: {str_alice}, Bob ID: {str_bob}, Conv ID: {str_conv}')

if __name__ == '__main__':
    provision()
