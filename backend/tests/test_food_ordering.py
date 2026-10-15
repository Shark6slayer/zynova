import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    food_order_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_food_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    food_order_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": {"$in": ["food_customer_1", "food_customer_2"]}})
        await db.food_orders.delete_many({"customer_name": {"$in": ["Food Customer One", "Food Customer Two"]}})
    await close_database_connection()

@pytest.mark.asyncio
async def test_food_discovery_and_ordering_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            await db.users.delete_many({"username": {"$in": ["food_customer_1", "food_customer_2"]}})

        # 1. Register customers
        reg1 = await client.post("/api/v1/auth/register", json={
            "email": "customer1@superai.in",
            "username": "food_customer_1",
            "full_name": "Food Customer One",
            "password": "Password123!"
        })
        assert reg1.status_code == 201

        login1 = await client.post("/api/v1/auth/login", json={
            "email": "customer1@superai.in",
            "password": "Password123!"
        })
        tok1 = login1.json()["access_token"]
        h1 = {"Authorization": f"Bearer {tok1}"}

        reg2 = await client.post("/api/v1/auth/register", json={
            "email": "customer2@superai.in",
            "username": "food_customer_2",
            "full_name": "Food Customer Two",
            "password": "Password123!"
        })
        assert reg2.status_code == 201

        login2 = await client.post("/api/v1/auth/login", json={
            "email": "customer2@superai.in",
            "password": "Password123!"
        })
        tok2 = login2.json()["access_token"]
        h2 = {"Authorization": f"Bearer {tok2}"}

        # 2. Browse Restaurants & filter
        all_rest = await client.get("/api/v1/food/restaurants")
        assert all_rest.status_code == 200
        restaurants = all_rest.json()
        assert len(restaurants) >= 3

        veg_rest = await client.get("/api/v1/food/restaurants?veg_only=true")
        assert veg_rest.status_code == 200
        assert all(r["is_veg"] is True for r in veg_rest.json())

        # 3. Retrieve Restaurant Menu
        rest_id = restaurants[0]["id"]
        detail_res = await client.get(f"/api/v1/food/restaurants/{rest_id}")
        assert detail_res.status_code == 200
        rest_detail = detail_res.json()
        assert "menu" in rest_detail
        assert len(rest_detail["menu"]) >= 2
        item_1 = rest_detail["menu"][0]
        item_2 = rest_detail["menu"][1]

        # 4. Place Order with Authoritative Server-side Price Calculation
        order_payload = {
            "restaurant_id": rest_id,
            "items": [
                {"item_id": item_1["id"], "quantity": 2},
                {"item_id": item_2["id"], "quantity": 1}
            ],
            "delivery_address": "Flat 402, Embassy Habitat, 100ft Road, Indiranagar, Bengaluru",
            "payment_method": "cod"
        }
        order_res = await client.post("/api/v1/food/orders", headers=h1, json=order_payload)
        assert order_res.status_code == 201
        order_data = order_res.json()
        order_id = order_data["id"]

        # Validate integer paise calculations
        expected_subtotal = (item_1["price_paise"] * 2) + (item_2["price_paise"] * 1)
        expected_delivery_fee = 3500
        expected_taxes = round(expected_subtotal * 0.05)
        expected_total = expected_subtotal + expected_delivery_fee + expected_taxes

        assert order_data["subtotal_paise"] == expected_subtotal
        assert order_data["delivery_fee_paise"] == expected_delivery_fee
        assert order_data["taxes_paise"] == expected_taxes
        assert order_data["total_paise"] == expected_total
        assert order_data["order_status"] == "placed"
        assert order_data["payment_method"] == "cod"

        # 5. Customer Order History
        orders_res = await client.get("/api/v1/food/orders", headers=h1)
        assert orders_res.status_code == 200
        my_orders = orders_res.json()
        assert any(o["id"] == order_id for o in my_orders)

        # 6. Customer Isolation (Customer 2 cannot view Customer 1's order)
        unauth_view = await client.get(f"/api/v1/food/orders/{order_id}", headers=h2)
        assert unauth_view.status_code == 403

        # 7. Customer Can View Their Own Order Details
        auth_view = await client.get(f"/api/v1/food/orders/{order_id}", headers=h1)
        assert auth_view.status_code == 200
        assert auth_view.json()["id"] == order_id

        # 8. Cancel Order
        cancel_res = await client.post(f"/api/v1/food/orders/{order_id}/cancel", headers=h1)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["order_status"] == "cancelled"

        # Cancelling already cancelled order should fail
        cancel_again = await client.post(f"/api/v1/food/orders/{order_id}/cancel", headers=h1)
        assert cancel_again.status_code == 400


@pytest.mark.asyncio
async def test_restaurant_partner_operations_and_ownership():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            await db.users.delete_many({"username": {"$in": ["rest_owner_1", "rest_owner_2", "food_buyer_1"]}})
            await db.restaurants.delete_many({"name": {"$in": ["Karthik Biryani House", "Rival Cafe"]}})
            await db.menu_items.delete_many({"name": "Special Mutton Biryani"})

        # 1. Register Owner 1 and Owner 2
        await client.post("/api/v1/auth/register", json={
            "email": "owner1@superai.in",
            "username": "rest_owner_1",
            "full_name": "Karthik Chef",
            "password": "Password123!"
        })
        l1 = await client.post("/api/v1/auth/login", json={"email": "owner1@superai.in", "password": "Password123!"})
        assert l1.status_code == 200
        h_o1 = {"Authorization": f"Bearer {l1.json()['access_token']}"}

        await client.post("/api/v1/auth/register", json={
            "email": "owner2@superai.in",
            "username": "rest_owner_2",
            "full_name": "Rival Chef",
            "password": "Password123!"
        })
        l2 = await client.post("/api/v1/auth/login", json={"email": "owner2@superai.in", "password": "Password123!"})
        assert l2.status_code == 200
        h_o2 = {"Authorization": f"Bearer {l2.json()['access_token']}"}

        # 2. Owner 1 registers restaurant
        rest_payload = {
            "name": "Karthik Biryani House",
            "description": "Authentic Dum Biryanis and Kebabs",
            "service_area": "Indiranagar",
            "address": "45 Biryani Lane, Indiranagar, Bengaluru",
            "cuisine": "Biryani, North Indian",
            "price_for_two_inr": 600,
            "is_veg": False,
            "is_open": True
        }
        res_r = await client.post("/api/v1/food/owner/restaurant", json=rest_payload, headers=h_o1)
        assert res_r.status_code == 201
        r_data = res_r.json()
        rest_id = r_data["id"]
        assert r_data["name"] == "Karthik Biryani House"
        assert r_data["is_open"] is True

        # Owner 2 registers restaurant
        res_r2 = await client.post("/api/v1/food/owner/restaurant", json={
            "name": "Rival Cafe",
            "service_area": "Koramangala",
            "address": "12 Coffee Street, Koramangala",
            "cuisine": "Cafe, Continental",
            "price_for_two_inr": 450,
            "is_veg": True,
            "is_open": True
        }, headers=h_o2)
        assert res_r2.status_code == 201
        r2_id = res_r2.json()["id"]

        # 3. Owner 1 creates Menu Item
        menu_payload = {
            "name": "Special Mutton Biryani",
            "category": "Main Course",
            "price_paise": 38000,  # ₹380.00
            "description": "Fragrant Seeraga Samba rice with tender mutton cuts.",
            "is_veg": False,
            "is_available": True
        }
        res_item = await client.post("/api/v1/food/owner/menu", json=menu_payload, headers=h_o1)
        assert res_item.status_code == 201
        item_data = res_item.json()
        item_id = item_data["id"]
        assert item_data["name"] == "Special Mutton Biryani"
        assert item_data["price_paise"] == 38000
        assert item_data["price_inr"] == 380.00

        # 4. Cross-Restaurant Tampering Rejection
        # Owner 2 attempts to edit Owner 1's menu item
        tamper_item = await client.patch(
            f"/api/v1/food/owner/menu/{item_id}",
            json={"price_paise": 100},
            headers=h_o2
        )
        assert tamper_item.status_code == 403
        assert "Forbidden" in tamper_item.json()["detail"]

        # Owner 1 updates own menu item
        valid_item_edit = await client.patch(
            f"/api/v1/food/owner/menu/{item_id}",
            json={"price_paise": 39500, "is_available": True},
            headers=h_o1
        )
        assert valid_item_edit.status_code == 200
        assert valid_item_edit.json()["price_paise"] == 39500

        # 5. Customer places order from Owner 1's restaurant
        await client.post("/api/v1/auth/register", json={
            "email": "foodbuyer@superai.in",
            "username": "food_buyer_1",
            "full_name": "Food Buyer",
            "password": "Password123!"
        })
        l_buyer = await client.post("/api/v1/auth/login", json={"email": "foodbuyer@superai.in", "password": "Password123!"})
        assert l_buyer.status_code == 200
        h_buyer = {"Authorization": f"Bearer {l_buyer.json()['access_token']}"}

        order_res = await client.post("/api/v1/food/orders", json={
            "restaurant_id": rest_id,
            "items": [{"item_id": item_id, "quantity": 2}],
            "delivery_address": "Flat 303, HAL 2nd Stage, Indiranagar",
            "payment_method": "cod"
        }, headers=h_buyer)
        assert order_res.status_code == 201
        placed_order = order_res.json()
        placed_order_id = placed_order["id"]

        # 6. Restaurant Owner Views Orders
        o1_orders = await client.get("/api/v1/food/owner/orders", headers=h_o1)
        assert o1_orders.status_code == 200
        assert any(o["id"] == placed_order_id for o in o1_orders.json())

        # Owner 2 should NOT see this order
        o2_orders = await client.get("/api/v1/food/owner/orders", headers=h_o2)
        assert o2_orders.status_code == 200
        assert not any(o["id"] == placed_order_id for o in o2_orders.json())

        # 7. Owner Order Status Transitions: placed -> confirmed -> preparing -> out_for_delivery -> delivered
        # Invalid transition (cannot skip to delivered directly from placed)
        inv_st = await client.patch(
            f"/api/v1/food/owner/orders/{placed_order_id}/status",
            json={"status": "delivered"},
            headers=h_o1
        )
        assert inv_st.status_code == 400

        # Valid: placed -> confirmed
        s_conf = await client.patch(
            f"/api/v1/food/owner/orders/{placed_order_id}/status",
            json={"status": "confirmed"},
            headers=h_o1
        )
        assert s_conf.status_code == 200
        assert s_conf.json()["order_status"] == "confirmed"

        # Valid: confirmed -> preparing
        s_prep = await client.patch(
            f"/api/v1/food/owner/orders/{placed_order_id}/status",
            json={"status": "preparing"},
            headers=h_o1
        )
        assert s_prep.status_code == 200
        assert s_prep.json()["order_status"] == "preparing"

        # Valid: preparing -> out_for_delivery
        s_out = await client.patch(
            f"/api/v1/food/owner/orders/{placed_order_id}/status",
            json={"status": "out_for_delivery"},
            headers=h_o1
        )
        assert s_out.status_code == 200
        assert s_out.json()["order_status"] == "out_for_delivery"

        # Valid: out_for_delivery -> delivered
        s_deliv = await client.patch(
            f"/api/v1/food/owner/orders/{placed_order_id}/status",
            json={"status": "delivered"},
            headers=h_o1
        )
        assert s_deliv.status_code == 200
        assert s_deliv.json()["order_status"] == "delivered"

