# 06 — DATABASE & API ARCHITECTURE

A comprehensive reference for MongoDB collections, schema definitions, indexing strategies, and core REST API route specifications.

---

## 1. MongoDB Collections & Schemas

### 1.1 `users` Collection
Stores core authentication credentials and profile preferences.
```json
{
  "_id": "ObjectId",
  "username": "string (unique, indexed)",
  "email": "string (unique, indexed)",
  "password_hash": "string (Argon2id format)",
  "full_name": "string",
  "avatar_url": "string (nullable)",
  "preferences": {
    "language": "string (default: 'en', ISO 639-1/3 code)",
    "theme": "string (default: 'dark')"
  },
  "is_active": "boolean (default: true)",
  "revoked_before": "ISODate (timestamp for global token invalidation)",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```
*Indices:* `{ username: 1 }` (unique), `{ email: 1 }` (unique).

### 1.2 `chat_messages` Collection
Stores encrypted real-time messages.
```json
{
  "_id": "ObjectId",
  "conversation_id": "ObjectId (indexed)",
  "sender_id": "ObjectId (indexed)",
  "encrypted_content": "string (base64 AES-256-GCM ciphertext)",
  "nonce": "string (base64)",
  "auth_tag": "string (base64)",
  "key_version": "string ('v1' | 'v2')",
  "created_at": "ISODate"
}
```
*Indices:* `{ conversation_id: 1, created_at: -1 }`.

### 1.3 `products` Collection (Zaviro Shopping)
Stores e-commerce product catalog.
```json
{
  "_id": "ObjectId",
  "title": "string",
  "description": "string",
  "seller_id": "ObjectId (indexed)",
  "price": "double (catalog display price)",
  "price_paise": "int64 (authoritative integer-paise representation)",
  "stock": "int (inventory quantity)",
  "category": "string (indexed)",
  "rating": "double",
  "images": ["string"],
  "created_at": "ISODate"
}
```
*Indices:* `{ category: 1 }`, `{ seller_id: 1 }`, text index on `{ title: "text", description: "text" }`.

### 1.4 `shopping_orders` Collection
Stores customer orders with server-calculated financial totals.
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (indexed)",
  "items": [
    {
      "product_id": "ObjectId",
      "title": "string",
      "quantity": "int",
      "unit_price_paise": "int64",
      "line_total_paise": "int64"
    }
  ],
  "subtotal_paise": "int64",
  "shipping_paise": "int64",
  "tax_paise": "int64 (18% GST)",
  "total_paise": "int64",
  "status": "string ('pending' | 'paid' | 'processing' | 'shipped' | 'delivered' | 'cancelled')",
  "idempotency_key": "string (unique, indexed)",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```
*Indices:* `{ user_id: 1, created_at: -1 }`, `{ idempotency_key: 1 }` (unique, sparse).

### 1.5 `audit_ledger_events` Collection
Immutable record of verified system actions.
```json
{
  "_id": "ObjectId",
  "schema_version": "string ('1.0.0')",
  "sequence_number": "int64 (unique, indexed)",
  "event_type": "string ('auth.login' | 'order.created' | 'order.cancelled')",
  "timestamp_utc": "string (ISO 8601)",
  "actor_pseudonym": "string (HMAC-SHA256 with secret salt)",
  "metadata": "object (minimal, zero PII)",
  "previous_event_hash": "string (hex SHA-256)",
  "event_hash": "string (hex SHA-256)",
  "created_at": "ISODate"
}
```
*Indices:* `{ sequence_number: 1 }` (unique).

---

## 2. Core REST API Route Specifications

| Method | Endpoint | Description | Auth Required | Rate Limited |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Create user profile | No | Yes (5/min) |
| `POST` | `/auth/login` | Authenticate & issue JWT | No | Yes (5/min) |
| `POST` | `/auth/logout` | Revoke active access token via JTI | Yes | No |
| `GET` | `/devices/sessions` | List active user device sessions | Yes | No |
| `DELETE`| `/devices/sessions/{id}`| Revoke specific session | Yes | No |
| `GET` | `/chat/conversations` | List user conversation threads | Yes | No |
| `POST` | `/chat/messages` | Send encrypted chat message | Yes | Yes (60/min) |
| `GET` | `/social/feed` | Retrieve paginated social posts | Yes | No |
| `POST` | `/social/posts` | Publish new social post | Yes | Yes (10/min) |
| `GET` | `/video/feed` | Retrieve video stream list | Yes | No |
| `GET` | `/shopping/products` | Query product catalog | No | No |
| `POST` | `/shopping/orders` | Place e-commerce order (atomic stock) | Yes | Yes (Idempotent) |
| `POST` | `/shopping/orders/{id}/cancel` | Cancel order & restore inventory | Yes | Yes |
| `GET` | `/food/restaurants` | Browse available restaurants | No | No |
| `POST` | `/food/orders` | Place restaurant food order | Yes | Yes (Idempotent) |
| `POST` | `/payments/process` | Execute simulated payment | Yes | Yes (Idempotent) |
| `GET` | `/health` | Core server liveness check | No | No |
| `GET` | `/health/security` | Cryptographic KMS & ledger health | Yes (Admin) | No |
