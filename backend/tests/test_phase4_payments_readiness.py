import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.security import create_access_token
from app.core.rate_limit import payment_rate_limiter
from app.services.payment_provider import PaymentProviderInterface
from app.services.payment_risk_service import validate_tx_transition


@pytest.fixture(autouse=True)
async def setup_db():
    await connect_to_database()
    payment_rate_limiter.requests.clear()
    yield
    await close_database_connection()


@pytest.mark.asyncio
async def test_payment_provider_fails_closed_in_production():
    orig_env = os.environ.get("ENVIRONMENT")
    try:
        os.environ["ENVIRONMENT"] = "production"
        from app.core.config import settings
        orig_set = settings.ENVIRONMENT
        settings.ENVIRONMENT = "production"
        prov = PaymentProviderInterface()
        assert prov.is_production is True
        pay_res = await prov.process_payment("TX1", 10000, "test@oksbi", "bank_account", "1")
        vpa_res = await prov.verify_vpa("test@oksbi")
        bal_res = await prov.check_bank_balance("HDFC Bank", "XXXX1234")
        assert pay_res["status"] == "failed"
        assert vpa_res["is_valid"] is False
        assert bal_res["status"] == "unsupported"
    finally:
        settings.ENVIRONMENT = orig_set
        if orig_env is not None:
            os.environ["ENVIRONMENT"] = orig_env
        else:
            os.environ.pop("ENVIRONMENT", None)


@pytest.mark.asyncio
async def test_phase4_webhooks_refunds_disputes_risk_and_reconciliation():
    db = get_database()
    u1_id = ObjectId()
    u2_id = ObjectId()
    for uid, em, un in [(u1_id, "p4_u1@zenova.test", "p4_u1"), (u2_id, "p4_u2@zenova.test", "p4_u2")]:
        await db.users.delete_many({"email": em})
        await db.users.insert_one({
            "_id": uid, "email": em, "username": un, "full_name": un,
            "is_active": True, "is_verified": True, "created_at": datetime.now(timezone.utc),
        })
    await db.bank_accounts.delete_many({"user_id": {"$in": [str(u1_id), str(u2_id)]}})
    await db.payment_transactions.delete_many({"user_id": {"$in": [str(u1_id), str(u2_id)]}})
    await db.payment_refunds.delete_many({"user_id": {"$in": [str(u1_id), str(u2_id)]}})
    await db.payment_disputes.delete_many({"user_id": {"$in": [str(u1_id), str(u2_id)]}})

    h1 = {"Authorization": f"Bearer {create_access_token({'sub': str(u1_id), 'email': 'p4_u1@zenova.test'})}"}
    h2 = {"Authorization": f"Bearer {create_access_token({'sub': str(u2_id), 'email': 'p4_u2@zenova.test'})}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Link bank account & send ₹100 (10000 paise)
        acc = (await ac.post("/api/v1/payments/accounts", headers=h1, json={
            "bank_name": "HDFC Bank", "ifsc_code": "HDFC0000123", "account_number": "9988776655", "account_type": "savings"
        })).json()
        tx = (await ac.post("/api/v1/payments/send", headers=h1, json={
            "recipient_type": "upi_id", "recipient_identifier": "merchant@hdfcbank",
            "amount_paise": 10000, "source_type": "bank_account", "source_id": acc["id"],
            "idempotency_key": f"p4_tx_{u1_id}",
        })).json()
        tx_id = tx["id"]
        tx_ref = tx["transaction_ref"]

        # 2. Cross-user refund & dispute IDOR blocked (403)
        assert (await ac.post(f"/api/v1/payments/transactions/{tx_id}/refund", headers=h2, json={"reason": "IDOR test"})).status_code == 403
        assert (await ac.post(f"/api/v1/payments/transactions/{tx_id}/dispute", headers=h2, json={"category": "unauthorized", "description": "IDOR dispute"})).status_code == 403

        # 3. Partial refund (4000 paise) + Over-refund blocked (400) + Remaining refund (6000 paise)
        r_part = await ac.post(f"/api/v1/payments/transactions/{tx_id}/refund", headers=h1, json={"amount_paise": 4000, "reason": "Partial item return"})
        assert r_part.status_code == 200 and r_part.json()["lifecycle_state"] == "PARTIALLY_REFUNDED"
        r_over = await ac.post(f"/api/v1/payments/transactions/{tx_id}/refund", headers=h1, json={"amount_paise": 7000, "reason": "Over refund attempt"})
        assert r_over.status_code == 400
        r_rem = await ac.post(f"/api/v1/payments/transactions/{tx_id}/refund", headers=h1, json={"amount_paise": 6000, "reason": "Final refund"})
        assert r_rem.status_code == 200 and r_rem.json()["lifecycle_state"] == "REFUNDED"

        # 4. Dispute submission & listing
        r_disp = await ac.post(f"/api/v1/payments/transactions/{tx_id}/dispute", headers=h1, json={
            "category": "debited_not_credited", "description": "Merchant did not confirm order"
        })
        assert r_disp.status_code == 201 and r_disp.json()["status"] == "OPEN"
        r_disp_list = await ac.get("/api/v1/payments/disputes", headers=h1)
        assert r_disp_list.status_code == 200 and len(r_disp_list.json()) == 1

        # 5. Webhook HMAC forgery rejected (401), valid signature accepted (200), replay rejected (409)
        wh_body = json.dumps({"event_id": f"evt_{u1_id}", "transaction_ref": tx_ref, "state": "SUCCESS"}).encode("utf-8")
        os.environ["PAYMENTS_WEBHOOK_SECRET"] = "test_phase4_webhook_secret_32chars!!"
        assert (await ac.post("/api/v1/payments/webhooks/provider", content=wh_body, headers={"x-zenova-signature": "forged_sig"})).status_code == 401

        secret = os.environ["PAYMENTS_WEBHOOK_SECRET"]
        valid_sig = hmac.new(secret.encode("utf-8"), wh_body, hashlib.sha256).hexdigest()
        r_wh = await ac.post("/api/v1/payments/webhooks/provider", content=wh_body, headers={"x-zenova-signature": valid_sig})
        assert r_wh.status_code == 200 and r_wh.json()["lifecycle_state"] == "SUCCESS"
        r_wh_rep = await ac.post("/api/v1/payments/webhooks/provider", content=wh_body, headers={"x-zenova-signature": valid_sig})
        assert r_wh_rep.status_code == 409

        # 6. State machine validation
        assert validate_tx_transition("PENDING", "SUCCESS") is True
        assert validate_tx_transition("FAILED", "SUCCESS") is False

        # 7. Fraud Risk Hold after 3 recent failed transactions
        for i in range(3):
            await db.payment_transactions.insert_one({
                "user_id": str(u2_id), "transaction_ref": f"FAIL_{i}_{u2_id}",
                "status": "failed", "amount_paise": 1000, "created_at": datetime.now(timezone.utc),
            })
        acc2 = (await ac.post("/api/v1/payments/accounts", headers=h2, json={
            "bank_name": "ICICI Bank", "ifsc_code": "ICIC0000123", "account_number": "1122334455", "account_type": "savings"
        })).json()
        r_hold = await ac.post("/api/v1/payments/send", headers=h2, json={
            "recipient_type": "upi_id", "recipient_identifier": "rahul@oksbi",
            "amount_paise": 1000, "source_type": "bank_account", "source_id": acc2["id"],
            "idempotency_key": f"p4_hold_{u2_id}",
        })
        assert r_hold.status_code == 429

        # 8. Reconciliation summary
        r_rec = await ac.get("/api/v1/payments/reconciliation/summary", headers=h1)
        assert r_rec.status_code == 200 and r_rec.json()["total_transactions"] >= 1
