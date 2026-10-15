import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    payment_rate_limiter,
    balance_enquiry_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_payments_test_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    payment_rate_limiter.requests.clear()
    balance_enquiry_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": {"$in": ["pay_user_1", "pay_user_2"]}})
        await db.bank_accounts.delete_many({"nickname": {"$in": ["Test Salary Account", "User 2 Account"]}})
        await db.rupay_cards.delete_many({"nickname": {"$in": ["HDFC RuPay", "User 2 Card"]}})
        await db.payment_transactions.delete_many({"idempotency_key": {"$in": ["pay_idem_1", "pay_idem_dup"]}})
    await close_database_connection()

@pytest.mark.asyncio
async def test_payments_upi_banking_and_rupay_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            await db.users.delete_many({"username": {"$in": ["pay_user_1", "pay_user_2"]}})

        # 1. Register User 1 & User 2
        await client.post("/api/v1/auth/register", json={
            "email": "pay1@superai.in",
            "username": "pay_user_1",
            "full_name": "Payment User One",
            "password": "Password123!"
        })
        login1 = await client.post("/api/v1/auth/login", json={
            "email": "pay1@superai.in",
            "password": "Password123!"
        })
        h1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        await client.post("/api/v1/auth/register", json={
            "email": "pay2@superai.in",
            "username": "pay_user_2",
            "full_name": "Payment User Two",
            "password": "Password123!"
        })
        login2 = await client.post("/api/v1/auth/login", json={
            "email": "pay2@superai.in",
            "password": "Password123!"
        })
        h2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # 2. Link Bank Account (Verify masking: never returns full account number)
        bank_res = await client.post("/api/v1/payments/accounts", json={
            "bank_name": "State Bank of India",
            "ifsc_code": "SBIN0001234",
            "account_number": "12345678901234",
            "account_type": "savings",
            "nickname": "Test Salary Account"
        }, headers=h1)
        assert bank_res.status_code == 201
        acc = bank_res.json()
        assert acc["masked_account_number"] == "••••••••1234"
        assert "12345678901234" not in str(acc)
        assert acc["is_default"] is True
        acc_id = acc["id"]

        # 3. Bank Balance Enquiry (Verified through provider adapter)
        bal_res = await client.get(f"/api/v1/payments/accounts/{acc_id}/balance", headers=h1)
        assert bal_res.status_code == 200
        assert bal_res.json()["balance_paise"] == 5420000
        assert bal_res.json()["balance_inr"] == 54200.0
        assert bal_res.json()["last_balance_enquiry"] is not None

        # 4. Customer Isolation: User 2 cannot enquire User 1's balance
        cross_bal = await client.get(f"/api/v1/payments/accounts/{acc_id}/balance", headers=h2)
        assert cross_bal.status_code == 403

        # 5. Link Eligible RuPay Credit Card
        rupay_res = await client.post("/api/v1/payments/rupay-cards", json={
            "issuing_bank": "HDFC Bank",
            "last_four_digits": "8899",
            "expiry_month": 12,
            "expiry_year": 2028,
            "nickname": "HDFC RuPay"
        }, headers=h1)
        assert rupay_res.status_code == 201
        card = rupay_res.json()
        assert card["last_four_digits"] == "8899"
        assert card["network"] == "RuPay"
        assert card["is_credit_on_upi_eligible"] is True
        card_id = card["id"]

        # 6. RuPay-on-UPI Restriction: Cannot be used for peer-to-peer (P2P) transfers
        p2p_rupay = await client.post("/api/v1/payments/send", json={
            "recipient_type": "phone",
            "recipient_identifier": "9876543210",
            "amount_paise": 20000,
            "source_type": "rupay_credit_card",
            "source_id": card_id,
            "idempotency_key": "rupay_p2p_fail"
        }, headers=h1)
        assert p2p_rupay.status_code == 400
        assert "merchant payments only" in p2p_rupay.json()["detail"]

        # 7. Execute UPI Payment via Bank Account (Exact integer paise: ₹500.00 = 50000 paise)
        pay_res = await client.post("/api/v1/payments/send", json={
            "recipient_type": "upi_id",
            "recipient_identifier": "rahul@oksbi",
            "recipient_name": "Rahul Sharma",
            "amount_paise": 50000,
            "source_type": "bank_account",
            "source_id": acc_id,
            "note": "Dinner share",
            "idempotency_key": "pay_idem_1"
        }, headers=h1)
        assert pay_res.status_code == 201
        tx = pay_res.json()
        assert tx["status"] == "success"
        assert tx["amount_paise"] == 50000
        assert tx["amount_inr"] == 500.0
        assert tx["npci_ref"] is not None
        assert tx["recipient_name"] == "Rahul Sharma"
        tx_ref = tx["transaction_ref"]

        # 8. Idempotency Test: Retrying with same idempotency_key returns identical transaction without double debits
        pay_dup = await client.post("/api/v1/payments/send", json={
            "recipient_type": "upi_id",
            "recipient_identifier": "rahul@oksbi",
            "amount_paise": 50000,
            "source_type": "bank_account",
            "source_id": acc_id,
            "idempotency_key": "pay_idem_1"
        }, headers=h1)
        assert pay_dup.status_code == 201
        assert pay_dup.json()["transaction_ref"] == tx_ref

        # 9. Transaction History Ledger & Statements
        tx_list = await client.get("/api/v1/payments/transactions", headers=h1)
        assert tx_list.status_code == 200
        assert len(tx_list.json()) >= 1
        assert tx_list.json()[0]["transaction_ref"] == tx_ref

        # User 2 cannot view User 1's transactions
        tx_list_u2 = await client.get("/api/v1/payments/transactions", headers=h2)
        assert tx_list_u2.status_code == 200
        assert all(t["transaction_ref"] != tx_ref for t in tx_list_u2.json())

        # 10. BBPS Bill Fetch
        bill_res = await client.post("/api/v1/payments/billers/fetch", json={
            "category": "electricity",
            "biller_id": "bescom_blr",
            "customer_identifier": "1002345678"
        }, headers=h1)
        assert bill_res.status_code == 200
        bill = bill_res.json()
        assert bill["biller_id"] == "bescom_blr"
        assert bill["amount_paise"] > 0
        assert bill["amount_inr"] == round(bill["amount_paise"] / 100, 2)
        assert bill["is_test_fixture"] is True
