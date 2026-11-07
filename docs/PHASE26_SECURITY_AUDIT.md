# ZYNOVA CONNECT — SECURITY AUDIT & THREAT MODEL
**Application Security, Authorization Boundaries, Locked Chats, and DPDP Compliance**  

---

## 1. Threat Modeling & Mitigation Matrix

| Threat Vector | Severity | Mitigation Strategy in Zynova Connect |
| :--- | :--- | :--- |
| **Eavesdropping on Messages at Rest** | Critical | AES-256-GCM envelope encryption with KMS-derived keys (`crypto_kms.py`) and Signal Protocol E2EE for direct channels. |
| **Replay Attacks** | High | Nonce uniqueness checks in AES-GCM and monotonic sequence tracking in Double Ratchet. |
| **Unauthorized Message Access** | Critical | Strict participant-level database filtering: only authenticated room participants can query message history. |
| **Locked Chat PIN Bypass** | High | PINs are never stored in plaintext; hashed using Argon2id with unique salts per user. |
| **Spam / Message Flooding** | Medium | User-level token bucket rate limiter enforced on message dispatch (`check_chat_user_rate_limit`). |
| **Cross-User Leakage on Block** | High | Bidirectional block verification: blocked users are prevented from creating conversations or sending direct messages. |

---

## 2. Locked Chat Session Security

- **Argon2id Verification**: PIN verification occurs server-side without revealing or persisting plaintext credentials.
- **Privacy Preservation**: Locked conversations are masked in standard overview listings until unlocked with valid authentication.
