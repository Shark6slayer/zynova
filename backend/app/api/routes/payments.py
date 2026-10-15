from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import APIRouter, HTTPException, status, Depends, Query, Header, Request
from bson import ObjectId

from app.schemas.all_schemas import (
    BankAccountCreate,
    BankAccountResponse,
    RuPayCardCreate,
    RuPayCardResponse,
    SendPaymentPayload,
    PaymentTransactionResponse,
    BillFetchPayload,
    BillerResponse,
    BillDetailResponse
)
from app.database.client import get_database
from app.api.deps import get_current_user
from app.core.rate_limit import check_payment_rate_limit, check_balance_enquiry_rate_limit
from app.services.payment_provider import payment_provider
from app.services.notification_service import create_event_notification

router = APIRouter(prefix="/payments", tags=["UPI, Banking & Payments"])

# Verified BBPS Billers List
SUPPORTED_BILLERS: List[BillerResponse] = [
    BillerResponse(
        id="airtel_prepaid",
        category="mobile_prepaid",
        name="Airtel Prepaid",
        operator_code="AIRTEL",
        icon_name="Smartphone",
        sample_identifier_label="Mobile Number"
    ),
    BillerResponse(
        id="jio_prepaid",
        category="mobile_prepaid",
        name="Jio Prepaid",
        operator_code="JIO",
        icon_name="Smartphone",
        sample_identifier_label="Mobile Number"
    ),
    BillerResponse(
        id="bescom_blr",
        category="electricity",
        name="BESCOM (Bangalore Electricity)",
        operator_code="BESCOM",
        icon_name="Zap",
        sample_identifier_label="Consumer Account ID"
    ),
    BillerResponse(
        id="tata_power",
        category="electricity",
        name="Tata Power Mumbai",
        operator_code="TATAPOW",
        icon_name="Zap",
        sample_identifier_label="Consumer Number"
    ),
    BillerResponse(
        id="bwssb_water",
        category="water",
        name="BWSSB Water Bangalore",
        operator_code="BWSSB",
        icon_name="Droplet",
        sample_identifier_label="Water Connection RR Number"
    ),
    BillerResponse(
        id="indane_gas",
        category="gas",
        name="Indane LPG Cylinder",
        operator_code="INDANE",
        icon_name="Flame",
        sample_identifier_label="17-Digit LPG ID / Mobile"
    ),
    BillerResponse(
        id="tata_play_dth",
        category="dth",
        name="Tata Play DTH",
        operator_code="TATAPLAY",
        icon_name="Tv",
        sample_identifier_label="Subscriber ID"
    ),
    BillerResponse(
        id="act_broadband",
        category="broadband",
        name="ACT Fibernet Broadband",
        operator_code="ACT",
        icon_name="Wifi",
        sample_identifier_label="Account / Phone Number"
    ),
    BillerResponse(
        id="nhai_fastag",
        category="fastag",
        name="NHAI FASTag Recharge",
        operator_code="FASTAG",
        icon_name="Car",
        sample_identifier_label="Vehicle Registration Number"
    )
]

# Helper to mask account number: keeps only last 4 digits
def _mask_account(raw_acc: str) -> str:
    cleaned = raw_acc.strip()
    if len(cleaned) <= 4:
        return "••••" + cleaned
    return "••••••••" + cleaned[-4:]

# 1. List Linked Bank Accounts for Current User
@router.get("/accounts", response_model=List[BankAccountResponse])
async def list_bank_accounts(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return []

    cursor = db.bank_accounts.find({"user_id": current_user["id"]}).sort("created_at", -1)
    accounts = []
    async for acc in cursor:
        bal_p = acc.get("balance_paise")
        accounts.append(BankAccountResponse(
            id=str(acc["_id"]),
            user_id=acc["user_id"],
            bank_name=acc["bank_name"],
            ifsc_code=acc["ifsc_code"],
            masked_account_number=acc["masked_account_number"],
            account_type=acc.get("account_type", "savings"),
            nickname=acc.get("nickname"),
            is_default=acc.get("is_default", False),
            balance_paise=bal_p,
            balance_inr=round(bal_p / 100, 2) if bal_p is not None else None,
            last_balance_enquiry=acc.get("last_balance_enquiry"),
            provider_status=acc.get("provider_status", "connected"),
            is_seed_account=acc.get("is_seed_account", False),
            created_at=acc["created_at"]
        ))
    return accounts

# 2. Link a New Bank Account
@router.post("/accounts", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
async def link_bank_account(
    account_in: BankAccountCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    now = datetime.now(timezone.utc)
    masked_acc = _mask_account(account_in.account_number)

    # Check if this is the user's first account to make it default
    existing_count = await db.bank_accounts.count_documents({"user_id": current_user["id"]})
    is_default = (existing_count == 0)

    account_doc = {
        "user_id": current_user["id"],
        "bank_name": account_in.bank_name.strip(),
        "ifsc_code": account_in.ifsc_code.strip().upper(),
        "masked_account_number": masked_acc,
        "account_type": account_in.account_type,
        "nickname": account_in.nickname.strip() if account_in.nickname else None,
        "is_default": is_default,
        "balance_paise": None,
        "last_balance_enquiry": None,
        "provider_status": "connected",
        "is_seed_account": False,
        "created_at": now,
        "updated_at": now
    }

    res = await db.bank_accounts.insert_one(account_doc)
    acc_id = str(res.inserted_id)

    return BankAccountResponse(
        id=acc_id,
        user_id=account_doc["user_id"],
        bank_name=account_doc["bank_name"],
        ifsc_code=account_doc["ifsc_code"],
        masked_account_number=account_doc["masked_account_number"],
        account_type=account_doc["account_type"],
        nickname=account_doc["nickname"],
        is_default=account_doc["is_default"],
        balance_paise=None,
        balance_inr=None,
        last_balance_enquiry=None,
        provider_status="connected",
        is_seed_account=False,
        created_at=now
    )

# 3. Bank Account Balance Enquiry (Strict Rate-Limiting & Verification)
@router.get("/accounts/{account_id}/balance", response_model=BankAccountResponse)
async def check_account_balance(
    account_id: str,
    current_user: dict = Depends(get_current_user)
):
    check_balance_enquiry_rate_limit(current_user["id"])

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        obj_id = ObjectId(account_id)
        query = {"_id": obj_id}
    except Exception:
        query = {"_id": account_id}

    acc = await db.bank_accounts.find_one(query)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")

    if acc["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this bank account")

    # Query provider for verified balance
    provider_res = await payment_provider.check_bank_balance(acc["bank_name"], acc["masked_account_number"])
    bal_paise = provider_res["balance_paise"]
    now = provider_res["enquiry_time"]

    await db.bank_accounts.update_one(
        {"_id": acc["_id"]},
        {"$set": {"balance_paise": bal_paise, "last_balance_enquiry": now, "updated_at": now}}
    )

    return BankAccountResponse(
        id=str(acc["_id"]),
        user_id=acc["user_id"],
        bank_name=acc["bank_name"],
        ifsc_code=acc["ifsc_code"],
        masked_account_number=acc["masked_account_number"],
        account_type=acc.get("account_type", "savings"),
        nickname=acc.get("nickname"),
        is_default=acc.get("is_default", False),
        balance_paise=bal_paise,
        balance_inr=round(bal_paise / 100, 2),
        last_balance_enquiry=now,
        provider_status=acc.get("provider_status", "connected"),
        is_seed_account=acc.get("is_seed_account", False),
        created_at=acc["created_at"]
    )

# 4. List Linked RuPay Credit Cards (Credit on UPI)
@router.get("/rupay-cards", response_model=List[RuPayCardResponse])
async def list_rupay_cards(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return []

    cursor = db.rupay_cards.find({"user_id": current_user["id"]}).sort("created_at", -1)
    cards = []
    async for c in cursor:
        cards.append(RuPayCardResponse(
            id=str(c["_id"]),
            user_id=c["user_id"],
            issuing_bank=c["issuing_bank"],
            last_four_digits=c["last_four_digits"],
            nickname=c.get("nickname"),
            network="RuPay",
            is_credit_on_upi_eligible=True,
            provider_status=c.get("provider_status", "connected"),
            created_at=c["created_at"]
        ))
    return cards

# 5. Link an Eligible RuPay Credit Card (Strict: never stores full card, CVV, or PIN)
@router.post("/rupay-cards", response_model=RuPayCardResponse, status_code=status.HTTP_201_CREATED)
async def link_rupay_card(
    card_in: RuPayCardCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    now = datetime.now(timezone.utc)
    card_doc = {
        "user_id": current_user["id"],
        "issuing_bank": card_in.issuing_bank.strip(),
        "last_four_digits": card_in.last_four_digits,
        "expiry_month": card_in.expiry_month,
        "expiry_year": card_in.expiry_year,
        "nickname": card_in.nickname.strip() if card_in.nickname else None,
        "network": "RuPay",
        "is_credit_on_upi_eligible": True,
        "provider_status": "connected",
        "created_at": now,
        "updated_at": now
    }

    res = await db.rupay_cards.insert_one(card_doc)
    card_id = str(res.inserted_id)

    return RuPayCardResponse(
        id=card_id,
        user_id=card_doc["user_id"],
        issuing_bank=card_doc["issuing_bank"],
        last_four_digits=card_doc["last_four_digits"],
        nickname=card_doc["nickname"],
        network="RuPay",
        is_credit_on_upi_eligible=True,
        provider_status="connected",
        created_at=now
    )

# 6. Verify UPI ID / VPA
@router.get("/vpa/verify")
async def verify_vpa(
    vpa: str = Query(..., min_length=3, max_length=100),
    current_user: dict = Depends(get_current_user)
):
    return await payment_provider.verify_vpa(vpa)

# 7. Execute UPI Payment (P2P, P2M, Bill or Recharge with Strict Idempotency & Integer Paise)
@router.post("/send", response_model=PaymentTransactionResponse, status_code=status.HTTP_201_CREATED)
async def send_payment(
    payload: SendPaymentPayload,
    current_user: dict = Depends(get_current_user)
):
    check_payment_rate_limit(current_user["id"])

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    # Idempotency check: if transaction with this idempotency key already exists for this user, return it
    existing_tx = await db.payment_transactions.find_one({
        "idempotency_key": payload.idempotency_key,
        "user_id": current_user["id"]
    })
    if existing_tx:
        return PaymentTransactionResponse(
            id=str(existing_tx["_id"]),
            user_id=existing_tx["user_id"],
            transaction_ref=existing_tx["transaction_ref"],
            npci_ref=existing_tx.get("npci_ref"),
            recipient_type=existing_tx["recipient_type"],
            recipient_identifier=existing_tx["recipient_identifier"],
            recipient_name=existing_tx["recipient_name"],
            amount_paise=existing_tx["amount_paise"],
            amount_inr=round(existing_tx["amount_paise"] / 100, 2),
            fee_paise=existing_tx.get("fee_paise", 0),
            source_type=existing_tx["source_type"],
            source_id=existing_tx["source_id"],
            source_title=existing_tx["source_title"],
            category=existing_tx["category"],
            status=existing_tx["status"],
            failure_reason=existing_tx.get("failure_reason"),
            note=existing_tx.get("note"),
            idempotency_key=existing_tx["idempotency_key"],
            created_at=existing_tx["created_at"],
            updated_at=existing_tx["updated_at"]
        )

    # Validate payment source ownership
    source_title = "Bank Account"
    if payload.source_type == "bank_account":
        try:
            s_obj = ObjectId(payload.source_id)
            s_q = {"_id": s_obj, "user_id": current_user["id"]}
        except Exception:
            s_q = {"_id": payload.source_id, "user_id": current_user["id"]}

        bank_acc = await db.bank_accounts.find_one(s_q)
        if not bank_acc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected bank account not found or unauthorized")
        source_title = f"{bank_acc['bank_name']} ({bank_acc['masked_account_number'][-4:]})"
    elif payload.source_type == "rupay_credit_card":
        # RuPay Credit on UPI is only eligible for merchant payments per NPCI guidelines
        if payload.recipient_type not in ["merchant", "upi_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RuPay Credit Cards on UPI are strictly permitted for merchant payments only per NPCI guidelines."
            )
        try:
            c_obj = ObjectId(payload.source_id)
            c_q = {"_id": c_obj, "user_id": current_user["id"]}
        except Exception:
            c_q = {"_id": payload.source_id, "user_id": current_user["id"]}

        card = await db.rupay_cards.find_one(c_q)
        if not card:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected RuPay card not found or unauthorized")
        source_title = f"RuPay Card •••• {card['last_four_digits']}"

    # Determine category
    category = "p2m" if payload.recipient_type == "merchant" else "p2p"

    # Resolve recipient name if not provided
    rec_name = payload.recipient_name
    if not rec_name:
        vpa_info = await payment_provider.verify_vpa(payload.recipient_identifier)
        rec_name = vpa_info["recipient_name"]

    # Generate unique transaction reference
    tx_ref = f"UPI{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

    # Process via provider
    proc_res = await payment_provider.process_payment(
        transaction_ref=tx_ref,
        amount_paise=payload.amount_paise,
        recipient_identifier=payload.recipient_identifier,
        source_type=payload.source_type,
        source_id=payload.source_id
    )

    now = datetime.now(timezone.utc)
    status_str = proc_res.get("status", "success")
    npci_rrn = proc_res.get("npci_rrn")

    tx_doc = {
        "user_id": current_user["id"],
        "transaction_ref": tx_ref,
        "npci_ref": npci_rrn,
        "recipient_type": payload.recipient_type,
        "recipient_identifier": payload.recipient_identifier.strip(),
        "recipient_name": rec_name,
        "amount_paise": payload.amount_paise,
        "fee_paise": 0,
        "source_type": payload.source_type,
        "source_id": payload.source_id,
        "source_title": source_title,
        "category": category,
        "status": status_str,
        "failure_reason": proc_res.get("reason"),
        "note": payload.note.strip() if payload.note else None,
        "idempotency_key": payload.idempotency_key,
        "created_at": now,
        "updated_at": now
    }

    res = await db.payment_transactions.insert_one(tx_doc)
    tx_id = str(res.inserted_id)

    # Trigger notification
    await create_event_notification(
        recipient_user_id=current_user["id"],
        actor_user_id=None,
        category="system",
        event_type="payment_success",
        title=f"₹{round(payload.amount_paise / 100, 2)} Paid to {rec_name}",
        desc=f"UPI Ref: {npci_rrn} • Debited from {source_title}",
        navigation_target=f"payments:receipt:{tx_ref}",
        metadata={"transaction_ref": tx_ref, "npci_ref": npci_rrn, "amount_paise": payload.amount_paise},
        event_id=f"tx_notify_{tx_ref}"
    )

    return PaymentTransactionResponse(
        id=tx_id,
        user_id=tx_doc["user_id"],
        transaction_ref=tx_ref,
        npci_ref=npci_rrn,
        recipient_type=tx_doc["recipient_type"],
        recipient_identifier=tx_doc["recipient_identifier"],
        recipient_name=tx_doc["recipient_name"],
        amount_paise=tx_doc["amount_paise"],
        amount_inr=round(tx_doc["amount_paise"] / 100, 2),
        fee_paise=0,
        source_type=tx_doc["source_type"],
        source_id=tx_doc["source_id"],
        source_title=tx_doc["source_title"],
        category=tx_doc["category"],
        status=status_str,
        failure_reason=tx_doc.get("failure_reason"),
        note=tx_doc.get("note"),
        idempotency_key=payload.idempotency_key,
        created_at=now,
        updated_at=now
    )

# 8. List Transactions / Passbook Ledger
@router.get("/transactions", response_model=List[PaymentTransactionResponse])
async def list_transactions(
    category: Optional[str] = Query(None, pattern="^(all|p2p|p2m|bill|recharge)$"),
    status: Optional[str] = Query(None, pattern="^(all|success|pending|failed|reversed)$"),
    limit: int = Query(30, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    query: dict = {"user_id": current_user["id"]}
    if category and category != "all":
        query["category"] = category
    if status and status != "all":
        query["status"] = status

    cursor = db.payment_transactions.find(query).sort("created_at", -1).limit(limit)
    txs = []
    async for doc in cursor:
        txs.append(PaymentTransactionResponse(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            transaction_ref=doc["transaction_ref"],
            npci_ref=doc.get("npci_ref"),
            recipient_type=doc["recipient_type"],
            recipient_identifier=doc["recipient_identifier"],
            recipient_name=doc["recipient_name"],
            amount_paise=doc["amount_paise"],
            amount_inr=round(doc["amount_paise"] / 100, 2),
            fee_paise=doc.get("fee_paise", 0),
            source_type=doc["source_type"],
            source_id=doc["source_id"],
            source_title=doc.get("source_title", "Bank Account"),
            category=doc.get("category", "p2p"),
            status=doc.get("status", "success"),
            failure_reason=doc.get("failure_reason"),
            note=doc.get("note"),
            idempotency_key=doc.get("idempotency_key", ""),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"]
        ))
    return txs

# 9. Get Supported BBPS Billers by Category
@router.get("/billers", response_model=List[BillerResponse])
async def list_billers(category: Optional[str] = Query(None)):
    if category and category != "all":
        return [b for b in SUPPORTED_BILLERS if b.category == category]
    return SUPPORTED_BILLERS

# 10. BBPS Bill Fetch
@router.post("/billers/fetch", response_model=BillDetailResponse)
async def fetch_bill(
    payload: BillFetchPayload,
    current_user: dict = Depends(get_current_user)
):
    bill = await payment_provider.fetch_bbps_bill(
        category=payload.category,
        biller_id=payload.biller_id,
        customer_identifier=payload.customer_identifier
    )
    if not bill:
        raise HTTPException(status_code=404, detail="No active bill found for given account/consumer identifier")
    return BillDetailResponse(**bill)
