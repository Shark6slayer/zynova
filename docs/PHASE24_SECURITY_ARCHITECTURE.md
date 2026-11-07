# ZYNOVA 3.0 — PHASE 24: SECURITY & PRIVACY ARCHITECTURE
**Document ID:** DOC-PHASE24-SECURITY-001  
**Author:** Principal Application Security Engineer & Cryptographic Architect  
**Status:** Approved Architecture Specification  
**Scope:** Identity Isolation, End-to-End Encryption Planning, Moderation, and Rate Limiting  

---

## 1. EXECUTIVE SUMMARY

The convergence of Social, Connect, and Video platforms under a unified backend demands rigorous security boundaries to prevent cross-account privilege escalation, message eavesdropping, abuse, and automated scraping.

This architecture defines:
1. **End-to-End Encryption (E2EE) Roadmap for Zynova Connect**: Designing for the Double Ratchet Algorithm (Signal Protocol) without rolling unvetted custom crypto.
2. **Access Control & Multi-Tenant Cross-User Isolation**: Granular RBAC and ownership verification.
3. **Multi-Tier Rate Limiting**: Token-bucket throttling per IP, per user, and per platform action.
4. **Content Moderation & Abuse Reporting**: Automated toxicity detection, user blocking enforcement, and Ed25519 tamper-proof audit trails.

---

## 2. END-TO-END ENCRYPTION (E2EE) PLANNING FOR ZYNOVA CONNECT

### 2.1 Cryptographic Protocol Adoption
Zynova adheres strictly to industry-standard, mathematically validated cryptography:
- **Protocol**: **Signal Protocol (Double Ratchet Algorithm + X3DH Key Agreement)**.
- **Client Libraries**:
  - Web: `@privacyresearch/libsignal-protocol-typescript` or libsodium WebAssembly bindings.
  - Android (Capacitor/Native): `libsignal-client` / libsodium-jni.
- **Server Knowledge**: The FastAPI backend acts as a **zero-knowledge untrusted relay** for encrypted message payloads. The server cannot decrypt messages, voice notes, or media attachments exchanged between E2EE-enabled peers.

### 2.2 Key Exchange Topology (X3DH)
MongoDB stores public cryptographic identity keys in the `user_devices` collection:
- **Identity Key (IK)**: Long-term Ed25519 / Curve25519 identity key.
- **Signed Pre-Key (SPK)**: Medium-term Curve25519 key signed by IK, rotated every 30 days.
- **One-Time Pre-Keys (OPKs)**: Pool of 100 Curve25519 keys replenished as consumed by initiating peers.

```
[User A (Initiator)]                                [FastAPI Key Server]                           [User B (Recipient)]
         │                                                    │                                              │
         │──── Request Pre-Key Bundle for B ─────────────────►│                                              │
         │◄─── Return IK_B, SPK_B, OPK_B, Sig(SPK_B) ─────────│                                              │
         │                                                    │                                              │
  (Computes shared secrets                                    │                                              │
   via X3DH & initializes                                     │                                              │
   Double Ratchet)                                            │                                              │
         │                                                    │                                              │
         │──── Send Encrypted Initial Message ───────────────►│                                              │
         │     (Ciphertext + Ephemeral Key + OPK_ID)          │──── Forward Ciphertext & Headers ───────────►│
         │                                                    │                                              │
                                                                                                      (Validates signature,
                                                                                                       derives shared key,
                                                                                                       decrypts ciphertext)
```

---

## 3. ACCESS CONTROL & CROSS-USER ISOLATION

To prevent Insecure Direct Object References (IDOR):
1. **Ownership Predicates**: Every mutation (editing posts, deleting videos, leaving groups) asserts `creator_id == current_user.id` or checks designated admin permissions in `group_memberships`.
2. **Mutual Blocking Protocol**:
   - Stored in the `users` collection `blocked_users: List[ObjectId]`.
   - Verified at the database query level (via `$nin` projections) and gateway level.
   - If User A blocks User B:
     - User B cannot view User A's Social profile, posts, or stories.
     - User B cannot initiate Connect chats or calls with User A.
     - User B's comments on User A's videos are automatically hidden.
3. **Private Account Visibility**:
   - If `social_profile.is_private == true`, posts and reels are accessible *only* to verified accounts in `user_relationships` where `status == "accepted"`.

---

## 4. MULTI-TIER RATE LIMITING & ABUSE MITIGATION

Implemented at the API gateway layer via Redis Token Bucket algorithms (`slowapi` / custom Redis Lua scripts):

| Endpoint Category | Limit per User | Limit per IP (Unauthenticated) | Violation Penalty |
| :--- | :--- | :--- | :--- |
| **Auth & Login** | 5 requests / min | 10 requests / 15 min | HTTP 429 + 15 min temporary lockout |
| **Social Posts & Reels** | 10 posts / hour | 0 (Auth required) | HTTP 429 |
| **Comments & Likes** | 60 actions / min | 0 (Auth required) | Action throttling (prevent bot spam) |
| **Connect Messages** | 120 messages / min | 0 (Auth required) | Temporary 5-minute cooldown |
| **WebRTC Call Initiation** | 10 calls / hour | 0 (Auth required) | Cooldown period |
| **Media Presigned Upload** | 20 requests / hour | 0 (Auth required) | HTTP 429 |

---

## 5. CONTENT MODERATION & TAMPER-PROOF AUDIT LOGGING

1. **Automated Content Screening**:
   - Text inputs (captions, comments, channel bios) pass through regex pattern matching for phone numbers, spam URLs, and abusive terms.
   - Images pass through NSFSW hash matching (PhotoDNA / PDQ hashing) before being made public.
2. **Abuse Reporting Pipeline**:
   - `content_reports` collection logs reports against posts, comments, profiles, and videos.
   - Threshold triggering: Any asset receiving 5+ unique reports within 1 hour is automatically flagged for moderator review and hidden from global Explore feeds pending investigation.
3. **Ed25519 Audit Integration**:
   - Critical administrative actions (account suspensions, content takedowns, privacy setting changes) generate cryptographic signatures committed to the immutable `ed25519_audit_log` collection established in Phase 22.
