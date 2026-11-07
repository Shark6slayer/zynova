# ZYNOVA CONNECT — END-TO-END ENCRYPTION ARCHITECTURE
**Signal Protocol Double Ratchet, Prekey Bundles, and Forward Secrecy**  

---

## 1. Cryptographic Primitives

Zynova Connect strictly adheres to verified, independently reviewed cryptography specifications:
- **Diffie-Hellman Key Exchange**: Curve25519 (X25519 ECDH via `cryptography.hazmat`).
- **Key Derivation Function (KDF)**: HKDF-SHA256 (`cryptography.hazmat.primitives.kdf.hkdf`).
- **Symmetric Authenticated Encryption**: AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
- **Signatures**: Ed25519 for Identity and Prekey authentication.

---

## 2. Key Hierarchy & Prekey Bundles

1. **Identity Key (IK)**: Long-term X25519/Ed25519 keypair identifying the user's registered device.
2. **Signed Prekey (SPK)**: Medium-term key signed by the Identity Key.
3. **One-Time Prekeys (OPK)**: Pool of ephemeral keys consumed once during initial X3DH session establishment.

---

## 3. Double Ratchet Implementation

The ratchet engine (`app/core/e2ee_engine.py`) maintains three stateful chains:
1. **Root Chain**: Advances on each new DH ratchet exchange when the sender introduces a new ephemeral public key.
2. **Sending Chain**: Generates symmetric message keys for outgoing messages.
3. **Receiving Chain**: Generates symmetric message keys for incoming messages.

Provides forward secrecy (compromise of current keys does not compromise past messages) and future secrecy / break-in recovery.
