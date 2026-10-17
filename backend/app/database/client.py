from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from app.core.config import settings
import logging

import certifi
import urllib.parse

logger = logging.getLogger(__name__)

def sanitize_mongo_uri(uri: str) -> str:
    """Redacts credentials from MongoDB URI for safe diagnostic logging."""
    try:
        parsed = urllib.parse.urlsplit(uri)
        if parsed.password:
            netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
        return uri
    except Exception:
        return "mongodb://***"

class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

db_manager = DatabaseManager()

async def connect_to_database() -> None:
    """Initializes MongoDB async client with standard TLS CA bundles and creates required indexes."""
    try:
        safe_uri = sanitize_mongo_uri(settings.MONGODB_URI)
        logger.info(f"Connecting to MongoDB at {safe_uri}...")

        # Configure Motor/PyMongo with verified CA bundle from certifi
        client_kwargs = {
            "serverSelectionTimeoutMS": 5000,
            "connectTimeoutMS": 10000,
            "socketTimeoutMS": 10000,
        }
        
        # If connecting via TLS or Atlas SRV, explicitly use certifi CA bundle
        if "mongodb+srv://" in settings.MONGODB_URI or "tls=true" in settings.MONGODB_URI.lower() or "ssl=true" in settings.MONGODB_URI.lower():
            client_kwargs["tlsCAFile"] = certifi.where()

        db_manager.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            **client_kwargs
        )
        db_manager.db = db_manager.client[settings.MONGODB_DB_NAME]
        
        # Test connection ping
        await db_manager.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB!")

        # Setup indexes
        await _setup_indexes()
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB: {e}. Backend will operate in fallback state for readiness.")
        if db_manager.client:
            db_manager.client.close()
        db_manager.client = None
        db_manager.db = None

async def _setup_indexes() -> None:
    """Ensures unique and query indexes for collections."""
    if db_manager.db is None:
        return
    try:
        # Users indexes
        await db_manager.db.users.create_index("email", unique=True)
        await db_manager.db.users.create_index("username", unique=True)

        # User preferences indexes
        await db_manager.db.user_preferences.create_index("user_id", unique=True)

        # Conversations indexes
        await db_manager.db.conversations.create_index([("user_id", 1), ("updated_at", -1)])

        # Notifications indexes
        await db_manager.db.notifications.create_index([("user_id", 1), ("created_at", -1)])
        
        # Refresh tokens index with TTL
        await db_manager.db.refresh_tokens.create_index("token", unique=True)

        # Chat rooms indexes
        await db_manager.db.chat_rooms.create_index("participants")
        await db_manager.db.chat_rooms.create_index([("participants", 1), ("updated_at", -1)])

        # Chat messages indexes
        await db_manager.db.chat_messages.create_index([("conversation_id", 1), ("created_at", 1)])
        await db_manager.db.chat_messages.create_index([("conversation_id", 1), ("read_by", 1)])

        # Social Posts indexes
        await db_manager.db.posts.create_index([("created_at", -1)])
        await db_manager.db.posts.create_index([("author_id", 1), ("created_at", -1)])

        # Social Follows indexes (unique compound index prevents duplicate follows)
        await db_manager.db.follows.create_index([("follower_id", 1), ("following_id", 1)], unique=True)
        await db_manager.db.follows.create_index("following_id")

        # Social Comments indexes
        await db_manager.db.post_comments.create_index([("post_id", 1), ("created_at", 1)])

        # Social Reports indexes
        await db_manager.db.reports.create_index([("reporter_id", 1), ("target_id", 1)])

        # Search Text Indexes
        await db_manager.db.users.create_index([
            ("username", "text"),
            ("full_name", "text"),
            ("bio", "text")
        ], name="users_text_search")

        await db_manager.db.posts.create_index([
            ("content", "text"),
            ("author_username", "text"),
            ("author_full_name", "text")
        ], name="posts_text_search")

        # Video Platform Indexes
        await db_manager.db.videos.create_index([("visibility", 1), ("status", 1), ("created_at", -1)])
        await db_manager.db.videos.create_index([("owner_id", 1), ("created_at", -1)])
        await db_manager.db.video_comments.create_index([("video_id", 1), ("created_at", 1)])
        await db_manager.db.video_views.create_index([("video_id", 1), ("viewer_key", 1), ("created_at", -1)])

        # Food Discovery and Orders Indexes
        await db_manager.db.restaurants.create_index([("is_open", 1), ("service_area", 1)])
        await db_manager.db.menu_items.create_index([("restaurant_id", 1), ("is_available", 1)])
        await db_manager.db.food_orders.create_index([("customer_id", 1), ("created_at", -1)])
        await db_manager.db.food_orders.create_index([("restaurant_id", 1), ("order_status", 1)])

        # Shopping & E-Commerce Indexes (Phase 4I)
        await db_manager.db.products.create_index([("is_published", 1), ("category", 1)])
        await db_manager.db.products.create_index([("is_published", 1), ("price_paise", 1)])
        await db_manager.db.products.create_index([("sku", 1)], unique=True)
        await db_manager.db.shopping_orders.create_index([("customer_id", 1), ("created_at", -1)])
        await db_manager.db.shopping_orders.create_index([("idempotency_key", 1)], sparse=True)

        # Notification System Indexes (Phase 4K)
        await db_manager.db.notifications.create_index([("user_id", 1), ("created_at", -1)])
        await db_manager.db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
        await db_manager.db.notifications.create_index([("event_id", 1)], unique=True, sparse=True)

        # UPI, Banking & Payments Indexes (Phase 4J)
        await db_manager.db.bank_accounts.create_index([("user_id", 1), ("created_at", -1)])
        await db_manager.db.rupay_cards.create_index([("user_id", 1), ("created_at", -1)])
        await db_manager.db.payment_transactions.create_index([("user_id", 1), ("created_at", -1)])
        await db_manager.db.payment_transactions.create_index([("idempotency_key", 1)], unique=True, sparse=True)
        await db_manager.db.payment_transactions.create_index([("transaction_ref", 1)], unique=True)

        # Seed initial authentic restaurants and menus if empty
        await _seed_food_catalog()
        # Seed initial shopping products catalog if empty
        await _seed_shopping_catalog()

        logger.info("MongoDB collections and indexes verified.")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")



async def close_database_connection() -> None:
    """Closes MongoDB connection pool."""
    if db_manager.client:
        logger.info("Closing MongoDB connection pool...")
        db_manager.client.close()
        db_manager.client = None
        db_manager.db = None

def get_database() -> Optional[AsyncIOMotorDatabase]:
    """Dependency helper to access current async database."""
    return db_manager.db

async def _seed_food_catalog() -> None:
    """Seeds verified regional restaurants and menu items if collection is empty."""
    if db_manager.db is None:
        return
    count = await db_manager.db.restaurants.count_documents({})
    if count > 0:
        return

    logger.info("Seeding initial food restaurant catalog and menus...")
    restaurants_seed = [
        {
            "_id": "rest_01",
            "name": "A2B - Adyar Ananda Bhavan",
            "description": "Legendary South Indian vegetarian dining, fresh ghee dosas, traditional sweets and filter coffee.",
            "service_area": "Indiranagar",
            "address": "100ft Road, HAL 2nd Stage, Indiranagar, Bengaluru, Karnataka 560038",
            "cuisine": "South Indian, Pure Veg",
            "rating": 4.6,
            "time_mins": 22,
            "price_for_two_inr": 350,
            "is_veg": True,
            "image_url": "https://images.unsplash.com/photo-1610192244261-3f33de3f55e4?w=600&auto=format&fit=crop&q=80",
            "is_open": True,
            "menu_items": [
                {
                    "_id": "dish_01_1",
                    "name": "Special Ghee Roast Masala Dosa",
                    "description": "Crispy golden crepe with potato masala and aromatic clarified butter served with 3 chutneys & sambar.",
                    "price_paise": 16000,
                    "is_veg": True,
                    "is_available": True,
                    "category": "Tiffin",
                    "image_url": "https://images.unsplash.com/photo-1610192244261-3f33de3f55e4?w=400&auto=format&fit=crop&q=80"
                },
                {
                    "_id": "dish_01_2",
                    "name": "South Indian Kumbakonam Degree Filter Coffee",
                    "description": "Traditional chicory blend frothed with hot rich milk in brass dabarah.",
                    "price_paise": 4500,
                    "is_veg": True,
                    "is_available": True,
                    "category": "Beverages",
                    "image_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=400&auto=format&fit=crop&q=80"
                },
                {
                    "_id": "dish_01_3",
                    "name": "Steamed Button Idli Sambar Dip",
                    "description": "Mini rice cakes soaked in piping hot spicy lentil stew with ghee drizzle.",
                    "price_paise": 12000,
                    "is_veg": True,
                    "is_available": True,
                    "category": "Tiffin",
                    "image_url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=400&auto=format&fit=crop&q=80"
                }
            ]
        },
        {
            "_id": "rest_02",
            "name": "Meghana Foods",
            "description": "Iconic spicy Andhra-style biryani, rich chicken starters and aromatic coastal curries.",
            "service_area": "Indiranagar",
            "address": "CMH Road, Indiranagar, Bengaluru, Karnataka 560038",
            "cuisine": "Andhra, Biryani",
            "rating": 4.8,
            "time_mins": 30,
            "price_for_two_inr": 650,
            "is_veg": False,
            "image_url": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&auto=format&fit=crop&q=80",
            "is_open": True,
            "menu_items": [
                {
                    "_id": "dish_02_1",
                    "name": "Special Chicken Boneless Biryani",
                    "description": "Signature basmati rice layered with spiced tender chicken fillets, served with raita and mirchi ka salan.",
                    "price_paise": 32000,
                    "is_veg": False,
                    "is_available": True,
                    "category": "Biryani",
                    "image_url": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400&auto=format&fit=crop&q=80"
                },
                {
                    "_id": "dish_02_2",
                    "name": "Andhra Chilli Chicken Dry",
                    "description": "Deep-fried succulent chicken tossed in green chilies, curry leaves and roasted garlic.",
                    "price_paise": 28000,
                    "is_veg": False,
                    "is_available": True,
                    "category": "Starters",
                    "image_url": "https://images.unsplash.com/photo-1527477378377-17e940f92606?w=400&auto=format&fit=crop&q=80"
                }
            ]
        },
        {
            "_id": "rest_03",
            "name": "The Rameshwaram Cafe",
            "description": "Bangalore's quintessential high-energy quick service eatery famed for Podi ghee dosas and idlis.",
            "service_area": "Indiranagar",
            "address": "12th Main Road, Indiranagar, Bengaluru, Karnataka 560038",
            "cuisine": "Authentic South Indian",
            "rating": 4.9,
            "time_mins": 25,
            "price_for_two_inr": 300,
            "is_veg": True,
            "image_url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&auto=format&fit=crop&q=80",
            "is_open": True,
            "menu_items": [
                {
                    "_id": "dish_03_1",
                    "name": "Ghee Podi Thatte Idli (2 Pcs)",
                    "description": "Plate-sized spongy steamed idli smothered in spicy gunpowder podi and steaming hot pure desi ghee.",
                    "price_paise": 14000,
                    "is_veg": True,
                    "is_available": True,
                    "category": "Tiffin",
                    "image_url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=400&auto=format&fit=crop&q=80"
                },
                {
                    "_id": "dish_03_2",
                    "name": "Open Butter Garlic Masala Dosa",
                    "description": "Crispy open-faced dosa seasoned with house garlic chutney and white butter slab.",
                    "price_paise": 17000,
                    "is_veg": True,
                    "is_available": True,
                    "category": "Dosas",
                    "image_url": "https://images.unsplash.com/photo-1610192244261-3f33de3f55e4?w=400&auto=format&fit=crop&q=80"
                }
            ]
        }
    ]

    for rest in restaurants_seed:
        menu_items = rest.pop("menu_items")
        await db_manager.db.restaurants.insert_one(rest)
        for item in menu_items:
            item["restaurant_id"] = rest["_id"]
            await db_manager.db.menu_items.insert_one(item)

    logger.info("Food catalog seeding complete.")
    from datetime import datetime, timezone

async def _seed_shopping_catalog() -> None:
    """Seeds verified authentic development seed products if products collection is empty."""
    if db_manager.db is None:
        return
    count = await db_manager.db.products.count_documents({})
    if count > 0:
        return

    logger.info("Seeding initial shopping products catalog (development seed data)...")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    seed_products = [
        {
            "_id": "prod_01",
            "name": "boAt Airdopes 141 ANC TWS Earbuds",
            "brand": "boAt",
            "sku": "BOAT-AIR-141",
            "category": "Electronics",
            "description": "True wireless earbuds with Active Noise Cancellation (up to 32dB), 42 hours playback, ENx quad mics, and Beast Mode low latency for gaming.",
            "price_paise": 149900,  # ₹1,499.00
            "mrp_paise": 449000,    # ₹4,490.00
            "rating": 4.5,
            "reviews_count": 1284,
            "stock": 45,
            "is_available": True,
            "is_published": True,
            "is_seed_data": True,
            "images": [
                "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&auto=format&fit=crop&q=80"
            ],
            "features": [
                "32dB Active Noise Cancellation",
                "42 Hours Total Playback",
                "ENx Quad Mics for Clear Calls",
                "ASAP Fast Charge (10 mins = 150 mins)"
            ],
            "created_at": now,
            "updated_at": now
        },
        {
            "_id": "prod_02",
            "name": "Titan Neo Chronograph Analog Watch for Men",
            "brand": "Titan",
            "sku": "TITAN-NEO-CHRONO",
            "category": "Fashion",
            "description": "Premium masculine timepiece featuring deep midnight blue dial, surgical-grade stainless steel bracelet, quartz movement, and 5 ATM water resistance.",
            "price_paise": 599500,  # ₹5,995.00
            "mrp_paise": 799500,    # ₹7,995.00
            "rating": 4.8,
            "reviews_count": 642,
            "stock": 25,
            "is_available": True,
            "is_published": True,
            "is_seed_data": True,
            "images": [
                "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80"
            ],
            "features": [
                "Quartz Chronograph Movement",
                "Mineral Crystal Glass",
                "50m / 5 ATM Water Resistance",
                "24 Months Manufacturer Warranty"
            ],
            "created_at": now,
            "updated_at": now
        },
        {
            "_id": "prod_03",
            "name": "Puma Velocity Nitro 2 Running Shoes",
            "brand": "Puma",
            "sku": "PUMA-VEL-NITRO-2",
            "category": "Footwear",
            "description": "All-in-one lightweight neutral running shoes engineered with advanced NITRO FOAM for superior responsiveness and plush cushioning over any distance.",
            "price_paise": 649900,  # ₹6,499.00
            "mrp_paise": 1099900,   # ₹10,999.00
            "rating": 4.7,
            "reviews_count": 319,
            "stock": 18,
            "is_available": True,
            "is_published": True,
            "is_seed_data": True,
            "images": [
                "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80"
            ],
            "features": [
                "NITRO FOAM Nitrogen-infused Midsole",
                "PUMAGRIP Durable Rubber Outsole",
                "Engineered Breathable Mesh Upper",
                "Reflective Accents for Low-light Visibility"
            ],
            "created_at": now,
            "updated_at": now
        },
        {
            "_id": "prod_04",
            "name": "Kindle Paperwhite 16GB (11th Gen) - 6.8\" Display",
            "brand": "Amazon",
            "sku": "KINDLE-PW-16GB",
            "category": "Electronics",
            "description": "Now with a 6.8\" display and thinner borders, adjustable warm light, up to 10 weeks of battery life, and 20% faster page turns.",
            "price_paise": 1499900, # ₹14,999.00
            "mrp_paise": 1699900,   # ₹16,999.00
            "rating": 4.9,
            "reviews_count": 2150,
            "stock": 30,
            "is_available": True,
            "is_published": True,
            "is_seed_data": True,
            "images": [
                "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80"
            ],
            "features": [
                "300 ppi Glare-free Flush-front Display",
                "Adjustable Warm Backlight",
                "IPX8 Waterproof Rating",
                "USB-C Fast Charging"
            ],
            "created_at": now,
            "updated_at": now
        },
        {
            "_id": "prod_05",
            "name": "Nespresso Essenza Mini Coffee Machine",
            "brand": "Nespresso",
            "sku": "NESP-ESS-MINI",
            "category": "Home & Kitchen",
            "description": "Compact espresso coffee maker with 19 bar high-pressure pump, 2 programmable cup sizes (Espresso & Lungo), and rapid 25-second heat-up.",
            "price_paise": 1299900, # ₹12,999.00
            "mrp_paise": 1550000,   # ₹15,500.00
            "rating": 4.6,
            "reviews_count": 480,
            "stock": 12,
            "is_available": True,
            "is_published": True,
            "is_seed_data": True,
            "images": [
                "https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=600&auto=format&fit=crop&q=80"
            ],
            "features": [
                "19-Bar High Pressure Extraction",
                "Fast 25-Second Heat Up",
                "Eco Mode After 3 Minutes",
                "Includes Welcome Capsule Set"
            ],
            "created_at": now,
            "updated_at": now
        },
        {
            "_id": "prod_06",
            "name": "Ray-Ban Classic Polarized Aviator Sunglasses",
            "brand": "Ray-Ban",
            "sku": "RAYBAN-AV-001",
            "category": "Accessories",
            "description": "Timeless golden metal frame with G-15 crystal green polarized lenses offering 100% UV protection and high optical clarity.",
            "price_paise": 829000,  # ₹8,290.00
            "mrp_paise": 999000,    # ₹9,990.00
            "rating": 4.8,
            "reviews_count": 910,
            "stock": 15,
            "is_available": True,
            "is_published": True,
            "is_seed_data": True,
            "images": [
                "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=600&auto=format&fit=crop&q=80"
            ],
            "features": [
                "Polarized Anti-Glare Protection",
                "Arista Gold Metal Frame",
                "100% UVA & UVB Filtration",
                "Made in Italy with Case & Cloth"
            ],
            "created_at": now,
            "updated_at": now
        }
    ]

    for p in seed_products:
        await db_manager.db.products.insert_one(p)

    logger.info("Shopping products catalog seeded with 6 authentic items.")


