import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    shopping_order_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_shopping_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    shopping_order_rate_limiter.requests.clear()

    # Seed isolated test products fixture if missing
    from app.database.client import _seed_shopping_catalog
    from app.core.config import settings
    orig_env = settings.ENVIRONMENT
    orig_allow = settings.ALLOW_DEMO_SEEDING
    settings.ALLOW_DEMO_SEEDING = True
    await _seed_shopping_catalog()
    settings.ENVIRONMENT = orig_env
    settings.ALLOW_DEMO_SEEDING = orig_allow

    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": {"$in": ["shop_cust_1", "shop_cust_2", "seller_test_1", "seller_test_2", "buyer_test_1"]}})
        await db.shopping_orders.delete_many({"customer_name": {"$in": ["Shop Customer One", "Shop Customer Two", "Buyer User"]}})
        await db.sellers.delete_many({"email": {"$in": ["seller1@superai.in", "seller2@superai.in"]}})
        await db.products.delete_many({"_id": {"$regex": "^prod_seller_"}})
        # Restore stock of seed items if altered during tests
        await db.products.update_one({"_id": "prod_01"}, {"$set": {"stock": 45, "is_available": True}})
        await db.products.update_one({"_id": "prod_02"}, {"$set": {"stock": 25, "is_available": True}})
        await db.products.delete_many({"_id": "test_limited_prod"})
    await close_database_connection()

@pytest.mark.asyncio
async def test_shopping_catalog_and_filters():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Browse products (catalog verification)
        res = await client.get("/api/v1/shopping/products")
        assert res.status_code == 200
        prods = res.json()
        assert len(prods) >= 6
        p0 = prods[0]
        assert "price_paise" in p0
        assert "price_inr" in p0
        assert p0["price_inr"] == round(p0["price_paise"] / 100, 2)
        assert p0["is_seed_data"] is True

        # 2. Category filtering
        res_cat = await client.get("/api/v1/shopping/products?category=Electronics")
        assert res_cat.status_code == 200
        elec = res_cat.json()
        assert all(p["category"] == "Electronics" for p in elec)
        assert len(elec) >= 2

        # 3. Search filtering
        res_search = await client.get("/api/v1/shopping/products?search=Titan")
        assert res_search.status_code == 200
        titan_items = res_search.json()
        assert len(titan_items) >= 1
        assert "Titan" in titan_items[0]["name"] or "Titan" in titan_items[0]["brand"]

        # 4. Price range filtering & Sorting
        res_price = await client.get("/api/v1/shopping/products?min_price=100000&max_price=700000&sort=price_asc")
        assert res_price.status_code == 200
        filtered = res_price.json()
        assert len(filtered) > 0
        prices = [p["price_paise"] for p in filtered]
        assert prices == sorted(prices)
        assert all(100000 <= p <= 700000 for p in prices)

        # 5. Product detail
        res_detail = await client.get(f"/api/v1/shopping/products/{p0['id']}")
        assert res_detail.status_code == 200
        assert res_detail.json()["id"] == p0["id"]

@pytest.mark.asyncio
async def test_shopping_order_lifecycle_stock_and_cancellation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            await db.users.delete_many({"username": {"$in": ["shop_cust_1", "shop_cust_2"]}})
            # Insert a special item with stock 2 for atomic concurrency/oversell tests
            await db.products.insert_one({
                "_id": "test_limited_prod",
                "name": "Limited Edition Mechanical Keyboard",
                "brand": "Keychron",
                "sku": "KEYCHRON-K2-LTD",
                "category": "Electronics",
                "description": "Custom aluminum frame mechanical keyboard.",
                "price_paise": 799900,  # ₹7,999.00
                "stock": 2,
                "is_available": True,
                "is_published": True,
                "is_seed_data": True,
                "images": ["https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600"],
                "features": ["Gateron G Pro Brown Switches", "RGB Backlight"]
            })

        # 1. Register Customer 1 & 2
        await client.post("/api/v1/auth/register", json={
            "email": "shop1@superai.in",
            "username": "shop_cust_1",
            "full_name": "Shop Customer One",
            "password": "Password123!"
        })
        login1 = await client.post("/api/v1/auth/login", json={
            "email": "shop1@superai.in",
            "password": "Password123!"
        })
        h1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        await client.post("/api/v1/auth/register", json={
            "email": "shop2@superai.in",
            "username": "shop_cust_2",
            "full_name": "Shop Customer Two",
            "password": "Password123!"
        })
        login2 = await client.post("/api/v1/auth/login", json={
            "email": "shop2@superai.in",
            "password": "Password123!"
        })
        h2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # 2. Test exact integer-paise calculations on Order Creation
        # Subtotal: 799900 * 1 = 799900 paise (>= 99900 => free shipping 0 paise)
        # Taxes: 18% of 799900 = round(143982) paise
        # Total: 799900 + 0 + 143982 = 943882 paise
        order_payload = {
            "items": [{"product_id": "test_limited_prod", "quantity": 1}],
            "shipping_full_name": "Shop Customer One",
            "shipping_phone": "+919876543210",
            "shipping_address": "Flat 402, Highrise Heights, Indiranagar",
            "shipping_city": "Bengaluru",
            "shipping_postal_code": "560038",
            "payment_method": "cod",
            "idempotency_key": "idem_test_order_1"
        }
        create_res = await client.post("/api/v1/shopping/orders", json=order_payload, headers=h1)
        assert create_res.status_code == 201
        order_data = create_res.json()
        assert order_data["subtotal_paise"] == 799900
        assert order_data["shipping_paise"] == 0
        assert order_data["taxes_paise"] == 143982
        assert order_data["total_paise"] == 943882
        assert order_data["total_inr"] == 9438.82
        assert order_data["order_status"] == "placed"
        order_id = order_data["id"]

        # Stock should now be decremented from 2 to 1
        p_check = await client.get("/api/v1/shopping/products/test_limited_prod")
        assert p_check.json()["stock"] == 1

        # 3. Idempotency test: repeating with same idempotency_key returns identical order without double decrements
        repeat_res = await client.post("/api/v1/shopping/orders", json=order_payload, headers=h1)
        assert repeat_res.status_code == 201
        assert repeat_res.json()["id"] == order_id
        p_check2 = await client.get("/api/v1/shopping/products/test_limited_prod")
        assert p_check2.json()["stock"] == 1

        # 4. Oversell prevention: Customer 2 attempts to buy quantity 2 when stock is only 1
        oversell_payload = {
            "items": [{"product_id": "test_limited_prod", "quantity": 2}],
            "shipping_full_name": "Shop Customer Two",
            "shipping_phone": "+919876543211",
            "shipping_address": "Villa 12, Whitefield",
            "shipping_city": "Bengaluru",
            "shipping_postal_code": "560066",
            "payment_method": "test_mode_upi"
        }
        oversell_res = await client.post("/api/v1/shopping/orders", json=oversell_payload, headers=h2)
        assert oversell_res.status_code == 400
        assert "Insufficient stock" in oversell_res.json()["detail"] or "Stock just ran out" in oversell_res.json()["detail"]

        # 5. Customer 2 buys remaining 1 item
        valid_payload_2 = {
            "items": [{"product_id": "test_limited_prod", "quantity": 1}],
            "shipping_full_name": "Shop Customer Two",
            "shipping_phone": "+919876543211",
            "shipping_address": "Villa 12, Whitefield",
            "shipping_city": "Bengaluru",
            "shipping_postal_code": "560066",
            "payment_method": "test_mode_upi"
        }
        res2 = await client.post("/api/v1/shopping/orders", json=valid_payload_2, headers=h2)
        assert res2.status_code == 201
        assert res2.json()["payment_status"] == "simulated_paid"

        # Stock should now be 0, product unavailable
        p_zero = await client.get("/api/v1/shopping/products/test_limited_prod")
        assert p_zero.json()["stock"] == 0
        assert p_zero.json()["is_available"] is False

        # 6. Customer Order Isolation & Ownership Verification
        # Customer 2 cannot view Customer 1's order
        c2_get_c1 = await client.get(f"/api/v1/shopping/orders/{order_id}", headers=h2)
        assert c2_get_c1.status_code == 403

        # Customer 1 can view their own order
        c1_get = await client.get(f"/api/v1/shopping/orders/{order_id}", headers=h1)
        assert c1_get.status_code == 200
        assert c1_get.json()["id"] == order_id

        # 7. Customer Cancellation & Inventory Restoration
        cancel_res = await client.post(f"/api/v1/shopping/orders/{order_id}/cancel", headers=h1)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["order_status"] == "cancelled"

        # Stock must have been atomically restored from 0 to 1
        p_restored = await client.get("/api/v1/shopping/products/test_limited_prod")
        assert p_restored.json()["stock"] == 1
        assert p_restored.json()["is_available"] is True

        # Repeating cancellation fails
        repeat_cancel = await client.post(f"/api/v1/shopping/orders/{order_id}/cancel", headers=h1)
        assert repeat_cancel.status_code == 400


@pytest.mark.asyncio
async def test_seller_portal_lifecycle_and_ownership():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            await db.users.delete_many({"username": {"$in": ["seller_test_1", "seller_test_2", "buyer_test_1"]}})
            await db.sellers.delete_many({"business_name": {"$in": ["Karthik Crafts", "Rival Traders"]}})
            await db.products.delete_many({"name": "Handcrafted Brass Lamp"})

        # 1. Register Seller 1 and Seller 2
        await client.post("/api/v1/auth/register", json={
            "email": "seller1@superai.in",
            "username": "seller_test_1",
            "full_name": "Karthik Seller",
            "password": "Password123!"
        })
        l1 = await client.post("/api/v1/auth/login", json={"email": "seller1@superai.in", "password": "Password123!"})
        assert l1.status_code == 200
        h_s1 = {"Authorization": f"Bearer {l1.json()['access_token']}"}

        await client.post("/api/v1/auth/register", json={
            "email": "seller2@superai.in",
            "username": "seller_test_2",
            "full_name": "Rival Seller",
            "password": "Password123!"
        })
        l2 = await client.post("/api/v1/auth/login", json={"email": "seller2@superai.in", "password": "Password123!"})
        assert l2.status_code == 200
        h_s2 = {"Authorization": f"Bearer {l2.json()['access_token']}"}

        # 2. Seller 1 Onboarding
        reg_payload = {
            "business_name": "Karthik Crafts",
            "business_category": "Home & Living",
            "contact_phone": "+919876543299",
            "business_address": "88 Crafts Lane, Indiranagar",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560038",
            "gstin_or_pan": "29ABCDE1234F1Z5"
        }
        res_reg = await client.post("/api/v1/shopping/seller/register", json=reg_payload, headers=h_s1)
        assert res_reg.status_code == 201
        assert res_reg.json()["status"] == "approved"
        assert res_reg.json()["business_name"] == "Karthik Crafts"

        # Duplicate seller registration fails
        dup_reg = await client.post("/api/v1/shopping/seller/register", json=reg_payload, headers=h_s1)
        assert dup_reg.status_code == 400

        # Check Seller Profile
        res_prof = await client.get("/api/v1/shopping/seller/profile", headers=h_s1)
        assert res_prof.status_code == 200
        assert res_prof.json()["city"] == "Bengaluru"

        # 3. Create Product as Seller 1
        prod_payload = {
            "name": "Handcrafted Brass Lamp",
            "brand": "Karthik Crafts",
            "category": "Home & Living",
            "description": "Authentic traditional artisanal brass diya lamp.",
            "price_paise": 149900,  # ₹1,499.00
            "mrp_paise": 199900,
            "stock": 10,
            "images": ["https://images.unsplash.com/photo-1543269865-cbf427effbad?w=600"],
            "features": ["Pure Brass", "Hand-carved"]
        }
        res_p = await client.post("/api/v1/shopping/seller/products", json=prod_payload, headers=h_s1)
        assert res_p.status_code == 201
        p_data = res_p.json()
        prod_id = p_data["id"]
        assert p_data["seller_name"] == "Karthik Crafts"
        assert p_data["price_paise"] == 149900
        assert p_data["price_inr"] == 1499.00

        # Non-seller cannot create product
        non_seller_p = await client.post("/api/v1/shopping/seller/products", json=prod_payload, headers=h_s2)
        assert non_seller_p.status_code == 403  # Seller 2 hasn't registered as seller yet

        # 4. Cross-seller product tampering rejection
        # Register Seller 2 now
        await client.post("/api/v1/shopping/seller/register", json={
            "business_name": "Rival Traders",
            "business_category": "Electronics",
            "contact_phone": "+919876543277",
            "business_address": "404 Tech Park",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560100"
        }, headers=h_s2)

        # Seller 2 attempts to edit Seller 1's product
        tamper_res = await client.patch(
            f"/api/v1/shopping/seller/products/{prod_id}",
            json={"price_paise": 100},
            headers=h_s2
        )
        assert tamper_res.status_code == 403
        assert "Forbidden" in tamper_res.json()["detail"]

        # Seller 1 updates own product
        valid_edit = await client.patch(
            f"/api/v1/shopping/seller/products/{prod_id}",
            json={"price_paise": 139900, "stock": 15},
            headers=h_s1
        )
        assert valid_edit.status_code == 200
        assert valid_edit.json()["price_paise"] == 139900
        assert valid_edit.json()["stock"] == 15

        # 5. Customer places order containing Seller 1's product
        await client.post("/api/v1/auth/register", json={
            "email": "buyer1@superai.in",
            "username": "buyer_test_1",
            "full_name": "Buyer One",
            "password": "Password123!"
        })
        l_buyer = await client.post("/api/v1/auth/login", json={"email": "buyer1@superai.in", "password": "Password123!"})
        assert l_buyer.status_code == 200
        h_buyer = {"Authorization": f"Bearer {l_buyer.json()['access_token']}"}

        order_res = await client.post("/api/v1/shopping/orders", json={
            "items": [{"product_id": prod_id, "quantity": 2}],
            "shipping_full_name": "Buyer One",
            "shipping_phone": "+919876543210",
            "shipping_address": "Flat 101, Indiranagar",
            "shipping_city": "Bengaluru",
            "shipping_postal_code": "560038",
            "payment_method": "cod"
        }, headers=h_buyer)
        assert order_res.status_code == 201
        placed_order_id = order_res.json()["id"]

        # 6. Seller 1 views Seller Orders
        s1_orders = await client.get("/api/v1/shopping/seller/orders", headers=h_s1)
        assert s1_orders.status_code == 200
        assert any(o["id"] == placed_order_id for o in s1_orders.json())

        # Seller 2 should not see this order (no products owned by Seller 2)
        s2_orders = await client.get("/api/v1/shopping/seller/orders", headers=h_s2)
        assert s2_orders.status_code == 200
        assert not any(o["id"] == placed_order_id for o in s2_orders.json())

        # 7. Seller Order Status Transitions
        # Invalid status transition (e.g. directly to delivered without processing/shipped)
        inv_trans = await client.patch(
            f"/api/v1/shopping/seller/orders/{placed_order_id}/status",
            json={"status": "delivered"},
            headers=h_s1
        )
        assert inv_trans.status_code == 400

        # Valid transition: placed -> processing
        tr1 = await client.patch(
            f"/api/v1/shopping/seller/orders/{placed_order_id}/status",
            json={"status": "processing"},
            headers=h_s1
        )
        assert tr1.status_code == 200
        assert tr1.json()["order_status"] == "processing"

        # Valid transition: processing -> shipped
        tr2 = await client.patch(
            f"/api/v1/shopping/seller/orders/{placed_order_id}/status",
            json={"status": "shipped"},
            headers=h_s1
        )
        assert tr2.status_code == 200
        assert tr2.json()["order_status"] == "shipped"

        # 8. Live Seller Dashboard Analytics Verification
        dash_res = await client.get("/api/v1/shopping/seller/dashboard", headers=h_s1)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        assert dash_data["active_products"] >= 1
        assert dash_data["fulfilled_orders"] >= 1  # order is shipped/fulfilled
        # 2 units * ₹1399 = ₹2798.00 (279800 paise)
        assert dash_data["gross_sales_paise"] == 279800
        assert dash_data["gross_sales_inr"] == 2798.00

