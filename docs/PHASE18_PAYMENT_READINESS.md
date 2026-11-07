# PHASE 18 — PAYMENT GATEWAY INTEGRATION ARCHITECTURE

**Document Reference:** `ZYNOVA-DOC-PHASE18-PAYMENTS`  
**Execution Timestamp:** 2026-11-07T09:50:30+05:30  
**Evaluator:** Senior Application Security & Fintech Systems Engineer  

---

## 1. AUDIT OF EXISTING PAYMENT SUBSYSTEM

### Source Code Findings:
- **Frontend (`PaymentsView.tsx`):** Demonstrates QR code rendering, UPI intent launcher strings (`upi://pay?...`), and simulated payment verification.
- **Backend (`payments.py` & `payment_provider.py`):**
  - Defines `PaymentProviderInterface` configured to fail closed in production.
  - Implements `process_payment` generating synthetic 12-digit NPCI RRNs in test environments.
  - In production (`ENVIRONMENT=production`), bank balance queries fail closed with `unsupported`, preventing synthetic funds exposure.
  - **Status:** **100% Sandbox Simulation**. Zero live merchant settlement accounts are currently attached.

---

## 2. PRODUCTION PAYMENT GATEWAY ARCHITECTURE (RAZORPAY & CASHFREE)

```
┌──────────────┐          1. Create Order Intent         ┌─────────────────────────┐
│              ├────────────────────────────────────────►│  Zynova FastAPI Backend │
│              │◄────────────────────────────────────────┤  (Order ID + Signature) │
│              │        2. Return Secure Token           └────────────┬────────────┘
│  Zynova Web  │                                                      │
│  / Mobile UI │          3. Client SDK Invocation                    │ Create Razorpay
│              ├─────────────────────────────┐                        │ Order via API
│              │                             ▼                        ▼
│              │                 ┌───────────────────────┐   ┌─────────────────┐
│              │                 │   Razorpay / Cashfree │   │ Razorpay Servers │
│              │                 │   Checkout Modal      ├──►│ (UPI / RuPay)   │
│              │◄────────────────┤   (Bank / UPI App)    │   └────────┬────────┘
│              │  4. Client Ack  └───────────────────────┘            │
└──────┬───────┘                                                      │ 5. Asynchronous Webhook
       │                                                              │ (HMAC-SHA256 Signed)
       ▼                                                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Zynova Webhook Endpoint (`/api/v1/payments/webhook`)      │
│  - Verify `X-Razorpay-Signature` using Server-Side Secret Key          │
│  - Idempotency Check: `payment_intents.find_one({provider_order_id})`   │
│  - State Transition: `PENDING` -> `CAPTURED` or `FAILED`                │
│  - Persist Immutable Cryptographic Event to Ed25519 Audit Ledger       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. STRICT SECURITY & COMPLIANCE REQUIREMENTS

1. **Zero Client Trust:**
   - Under no circumstances will the backend accept client-provided `status: "success"` payloads to credit orders or wallets.
   - Order fulfillment is triggered **strictly** upon receipt of verified server-to-server webhook signatures.
2. **Server-Side HMAC-SHA256 Verification:**
   ```python
   def verify_razorpay_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
       payload = f"{order_id}|{payment_id}".encode("utf-8")
       expected_signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
       return hmac.compare_digest(expected_signature, signature)
   ```
3. **Idempotency Safeguards:**
   - Webhook deliveries are keyed by `event_id` and `payment_id` in MongoDB with a unique index. Duplicate webhook retries from Razorpay will produce an immediate HTTP 200 without duplicate database mutations.
4. **Refund & Ledger Reconciliation:**
   - Any initiated refund will record a paired debit transaction anchored in the sovereign Ed25519 audit chain.

