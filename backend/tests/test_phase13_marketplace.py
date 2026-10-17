import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.services.marketplace_reconciliation import run_marketplace_reconciliation
from app.core.rate_limit import (
    auth_rate_limiter,
    shopping_order_rate_limiter,
    payment_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_phase13_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    shopping_order_rate_limiter.requests.clear()
    payment_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": {"$in": ["p13_cust_1", "p13_cust_2", "p13_pay_user"]}})
        await db.shopping_orders.delete_many({"customer_email": {"$in": ["cust1@superai.in", "cust2@superai.in", "p13pay@superai.in"]}})
        await db.food_orders.delete_many({"customer_email": {"$in": ["cust1@superai.in", "cust2@superai.in", "p13pay@superai.in"]}})
        await db.payment_transactions.delete_many({"idempotency_key": {"$in": ["p13_pay_idem_1", "p13_pay_idem_2"]}})
        await db.bank_accounts.delete_many({"nickname": "P13 Salary Account"})
        await db.products.delete_many({"_id": {"$in": ["p13_test_prod_1", "p13_test_prod_2"]}})
    await close_database_connection()

@pytest.mark.asyncio
async def test_server_side_pricing_and_integer_paise_integrity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()

        # 1. Register customer
        await client.post("/api/v1/auth/register", json={
            "email": "cust1@superai.in",
            "username": "p13_cust_1",
            "full_name": "Phase 13 Customer One",
            "password": "Password123!"
        })
        login_res = await client.post("/api/v1/auth/login", json={
            "email": "cust1@superai.in",
            "password": "Password123!"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Insert test product with known price in integer paise
        # Price: 150000 paise (₹1500.00) -> free shipping (subtotal > ₹999 / 99900 paise)
        # GST 18% = 27000 paise -> Total = 177000 paise
        await db.products.delete_many({"_id": "p13_test_prod_1"})
        await db.products.insert_one({
            "_id": "p13_test_prod_1",
            "name": "Phase 13 Integrity Test Gadget",
            "brand": "SecureTech",
            "category": "Electronics",
            "price_paise": 150000,
            "stock": 10,
            "is_available": True,
            "is_published": True,
            "seller_id": "seller_abc"
        })

        # 3. Client submits order payload with ONLY item IDs and quantities
        # Client CANNOT tamper with prices, taxes, or totals
        order_payload = {
            "shipping_full_name": "Test Customer",
            "shipping_phone": "+919876543210",
            "shipping_address": "123 Security Blvd",
            "shipping_city": "Bengaluru",
            "shipping_postal_code": "560001",
            "payment_method": "test_mode_upi",
            "idempotency_key": "p13_order_idem_1",
            "items": [
                {"product_id": "p13_test_prod_1", "quantity": 1}
            ]
        }

        order_res = await client.post("/api/v1/shopping/orders", json=order_payload, headers=headers)
        assert order_res.status_code == 201
        order_data = order_res.json()

        assert order_data["subtotal_paise"] == 150000
        assert order_data["shipping_paise"] == 0  # Free shipping over 99900 paise
        assert order_data["taxes_paise"] == 27000  # 18% GST = 27000
        assert order_data["total_paise"] == 177000
        assert order_data["total_inr"] == 1770.00
        assert order_data["order_status"] == "placed"

        # Verify stock was decremented atomically
        updated_prod = await db.products.find_one({"_id": "p13_test_prod_1"})
        assert updated_prod["stock"] == 9

        # 4. Idempotency verification: Re-submitting the exact same order returns existing record without double-decrementing stock
        dup_res = await client.post("/api/v1/shopping/orders", json=order_payload, headers=headers)
        assert dup_res.status_code == 201
        dup_data = dup_res.json()
        assert dup_data["id"] == order_data["id"]

        prod_after_dup = await db.products.find_one({"_id": "p13_test_prod_1"})
        assert prod_after_dup["stock"] == 9  # Stock remains 9!

@pytest.mark.asyncio
async def test_atomic_inventory_restoration_on_cancellation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()

        # Register & Login
        await client.post("/api/v1/auth/register", json={
            "email": "cust1@superai.in",
            "username": "p13_cust_1",
            "full_name": "Phase 13 Customer One",
            "password": "Password123!"
        })
        login_res = await client.post("/api/v1/auth/login", json={
            "email": "cust1@superai.in",
            "password": "Password123!"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await db.products.delete_many({"_id": "p13_test_prod_2"})
        await db.products.insert_one({
            "_id": "p13_test_prod_2",
            "name": "Phase 13 Restorable Item",
            "brand": "RestoreCo",
            "category": "Home",
            "price_paise": 50000,
            "stock": 5,
            "is_available": True,
            "is_published": True,
            "seller_id": "seller_abc"
        })

        # Place order for 2 units
        order_res = await client.post("/api/v1/shopping/orders", json={
            "shipping_full_name": "Test Customer",
            "shipping_phone": "+919876543210",
            "shipping_address": "456 Cancellation Way",
            "shipping_city": "Mumbai",
            "shipping_postal_code": "400001",
            "payment_method": "test_mode_upi",
            "items": [{"product_id": "p13_test_prod_2", "quantity": 2}]
        }, headers=headers)
        assert order_res.status_code == 201
        order_id = order_res.json()["id"]

        # Stock is now 3
        prod_mid = await db.products.find_one({"_id": "p13_test_prod_2"})
        assert prod_mid["stock"] == 3

        # Cancel the order
        cancel_res = await client.post(f"/api/v1/shopping/orders/{order_id}/cancel", headers=headers)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["order_status"] == "cancelled"

        # Stock is restored to 5
        prod_restored = await db.products.find_one({"_id": "p13_test_prod_2"})
        assert prod_restored["stock"] == 5

        # Attempting to cancel an already cancelled order should fail (State transition violation)
        cancel_again = await client.post(f"/api/v1/shopping/orders/{order_id}/cancel", headers=headers)
        assert cancel_again.status_code == 400
        assert "cannot be cancelled in its current state" in cancel_again.json()["detail"]

@pytest.mark.asyncio
async def test_cross_customer_and_seller_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Customer 1 & Customer 2
        await client.post("/api/v1/auth/register", json={
            "email": "cust1@superai.in",
            "username": "p13_cust_1",
            "full_name": "Customer One",
            "password": "Password123!"
        })
        login1 = await client.post("/api/v1/auth/login", json={"email": "cust1@superai.in", "password": "Password123!"})
        h1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        await client.post("/api/v1/auth/register", json={
            "email": "cust2@superai.in",
            "username": "p13_cust_2",
            "full_name": "Customer Two",
            "password": "Password123!"
        })
        login2 = await client.post("/api/v1/auth/login", json={"email": "cust2@superai.in", "password": "Password123!"})
        h2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # Customer 1 places an order (using seed product prod_01)
        order_res = await client.post("/api/v1/shopping/orders", json={
            "shipping_full_name": "Customer One",
            "shipping_phone": "+919876543210",
            "shipping_address": "Street 1",
            "shipping_city": "Delhi",
            "shipping_postal_code": "110001",
            "payment_method": "cod",
            "items": [{"product_id": "prod_01", "quantity": 1}]
        }, headers=h1)
        assert order_res.status_code == 201
        order_id = order_res.json()["id"]

        # Customer 2 attempts to read Customer 1's order details -> FORBIDDEN (403)
        h2_get = await client.get(f"/api/v1/shopping/orders/{order_id}", headers=h2)
        assert h2_get.status_code == 403
        assert "Access denied" in h2_get.json()["detail"]

        # Customer 2 attempts to cancel Customer 1's order -> FORBIDDEN (403)
        h2_cancel = await client.post(f"/api/v1/shopping/orders/{order_id}/cancel", headers=h2)
        assert h2_cancel.status_code == 403

@pytest.mark.asyncio
async def test_simulated_payment_idempotency_and_ledger_reconciliation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User
        await client.post("/api/v1/auth/register", json={
            "email": "p13pay@superai.in",
            "username": "p13_pay_user",
            "full_name": "Payment User",
            "password": "Password123!"
        })
        login_res = await client.post("/api/v1/auth/login", json={"email": "p13pay@superai.in", "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Link Bank Account
        bank_res = await client.post("/api/v1/payments/accounts", json={
            "bank_name": "HDFC Bank",
            "ifsc_code": "HDFC0001234",
            "account_number": "123456789012",
            "account_type": "savings",
            "nickname": "P13 Salary Account"
        }, headers=headers)
        assert bank_res.status_code == 201
        acc_id = bank_res.json()["id"]

        # 1. Send Payment with Idempotency Key
        pay_payload = {
            "recipient_type": "upi_id",
            "recipient_identifier": "merchant@icici",
            "recipient_name": "Super AI Store",
            "amount_paise": 49900,
            "source_type": "bank_account",
            "source_id": acc_id,
            "note": "Phase 13 Marketplace Purchase",
            "idempotency_key": "p13_pay_idem_1"
        }

        pay1 = await client.post("/api/v1/payments/send", json=pay_payload, headers=headers)
        assert pay1.status_code == 201
        tx1 = pay1.json()
        assert tx1["status"] in ["success", "simulated_paid"]
        assert tx1["amount_paise"] == 49900

        # 2. Re-send identical payment with same idempotency key
        pay2 = await client.post("/api/v1/payments/send", json=pay_payload, headers=headers)
        assert pay2.status_code in [200, 201]
        tx2 = pay2.json()
        assert tx2["id"] == tx1["id"]
        assert tx2["transaction_ref"] == tx1["transaction_ref"]

        # 3. Test Marketplace & Ledger Reconciliation Scan
        rec_report = await run_marketplace_reconciliation()
        assert rec_report["status"] == "clean"
        assert rec_report["authoritative_source"] == "MongoDB (super_ai_db)"
        assert rec_report["metrics"]["payment_transactions_count"] >= 1
        assert "reconciliation_notes" in rec_report
