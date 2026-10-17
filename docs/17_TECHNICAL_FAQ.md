# 17 — TECHNICAL ARCHITECTURAL FAQ

A comprehensive question-and-answer guide addressing technical, architectural, cryptographic, and scaling inquiries for engineering leaders, hiring managers, and system auditors.

---

### Q1: Why build a unified super-application instead of decoupled standalone apps?
**A:** In mobile-first developing economies, users face severe device resource constraints: budget smartphones often have 32GB to 64GB of storage, limited RAM, and metered cellular data. Running 5–6 separate background daemons for messaging, social feeds, shopping, and food ordering wastes battery and megabytes of duplicate assets. SUPER_AI consolidates these core journeys into a single **14.2 MB native binary** sharing one runtime, one memory cache, and one unified cryptographic identity.

### Q2: Is the chat encryption true End-to-End Encryption (E2EE)?
**A:** No, and we document this transparently. SUPER_AI uses **server-side AES-256-GCM envelope encryption with context binding**. This ensures that raw message plaintexts are never stored in plaintext inside the database, and database backups are immune to dump leaks. However, the application server decrypts payloads in transient memory to facilitate push notifications and search indexing. True zero-knowledge client-side E2EE (using the Signal Protocol) is slated for Phase 16 on our roadmap.

### Q3: What is "Context Binding" in envelope encryption and why does it matter?
**A:** Traditional field-level encryption allows an attacker with database write access to copy an encrypted ciphertext block from a legitimate record (e.g., a benign message) and paste it into another record (e.g., a financial transaction), causing the server to decrypt it in the wrong context (a *ciphertext transplant attack*). By parameterizing HKDF-SHA256 with `info = "entity_type:entity_id"`, the derived key is unique to that specific row. Moving the ciphertext to any other record makes it mathematically undecryptable.

### Q4: Why use integer paise instead of standard floating-point numbers for currency?
**A:** IEEE 754 floating-point arithmetic (used by JavaScript `number` and Python `float`) cannot accurately represent decimal fractions like `0.1` or `0.05`. Over thousands of transactions, penny-rounding drift occurs, creating opportunities for financial exploits or reconciliation mismatches. By strictly storing all monetary values as **64-bit integer paise (`100 paise = 1 INR`)**, every calculation (subtotals, shipping fees, 18% GST) is exact, deterministic, and integer-bound.

### Q5: How does the private audit ledger differ from standard logging?
**A:** Standard application logs (e.g., log files or Elasticsearch indices) can be edited, truncated, or deleted by a system administrator without leaving cryptographic traces. SUPER_AI's audit ledger serializes every event using **RFC 8785 Canonical JSON (JCS)** and links them via **SHA-256 hash chaining** ($H_n = \text{SHA-256}(E_n \parallel H_{n-1})$). Any insertion, modification, deletion, or reordering of historical events breaks the hash chain, immediately alerting auditors.

### Q6: Does SUPER_AI store customer PII or transaction details on a public blockchain?
**A:** **Never.** Storing personal data on a public blockchain violates fundamental privacy principles (and regulations like India's DPDP Act and the EU GDPR) because blockchains are immutable and public. SUPER_AI only anchors periodic **zero-PII Merkle checkpoint hashes** containing the sequence range and the Ed25519 signature. The public chain merely acts as an immutable external witness verifying that the private ledger was not altered retroactively.

### Q7: How does the offline synchronization engine prevent duplicate orders?
**A:** Our offline engine enforces a strict architectural boundary: **Order placement and payment actions are explicitly barred from the offline queue**. Users can draft social posts, compose messages, and browse cached catalogs while offline. When an order is placed online, client requests submit a cryptographically generated `Idempotency-Key`. The server checks this key against existing orders in MongoDB; network retries return the existing transaction record rather than executing a duplicate charge.

### Q8: What are the prerequisites before SUPER_AI can go to public production?
**A:** As detailed in our Phase 14 certification report, SUPER_AI is **Ready for Controlled Staging**. Before public production release, four external integrations must be completed:
1. Transition master encryption keys from environment variables to an enterprise Cloud KMS / HSM (Google Cloud KMS or AWS KMS).
2. Attach an external clustered Redis cluster for multi-pod distributed token revocation.
3. Acquire an authorized commercial Payment Aggregator license and connect live banking rails (NPCI UPI 2.0 / Card networks).
4. Commission an independent third-party CREST-accredited gray-box penetration test.
