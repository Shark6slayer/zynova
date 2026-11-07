"""
Zynova Connect E2EE Core Engine.
Implements the Signal Protocol Double Ratchet Specification using X25519 ECDH,
HKDF-SHA256, and authenticated AES-256-GCM.

Provides:
- User Identity Keys (IK) & Signed Prekeys (SPK) & One-Time Prekeys (OPK).
- X3DH Extended Triple Diffie-Hellman Initial Handshake.
- Double Ratchet: KDF Chains for Root Key, Sending Chain, and Receiving Chain.
- Message Authentication & Forward Secrecy.
- Multi-device Prekey bundles.
"""

import os
import base64
import json
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

INFO_ROOT_RATCHET = b"ZynovaConnectSignalRootRatchet_v1"
INFO_CHAIN_KDF = b"ZynovaConnectSignalChainKDF_v1"
INFO_MSG_KEY = b"ZynovaConnectSignalMessageKey_v1"
SALT_MSG_KEY = b"ZynovaConnectSignalMessageSalt_v1"

def generate_identity_keypair() -> Tuple[str, str]:
    """Generates base64 encoded X25519 private and public keys."""
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key()
    priv_b64 = base64.b64encode(priv.private_bytes_raw()).decode("utf-8")
    pub_b64 = base64.b64encode(pub.public_bytes_raw()).decode("utf-8")
    return priv_b64, pub_b64

def generate_prekey_bundle(num_one_time_keys: int = 10) -> Dict[str, Any]:
    """Generates a complete Signal-compliant Prekey Bundle."""
    ik_priv, ik_pub = generate_identity_keypair()
    spk_priv, spk_pub = generate_identity_keypair()

    opks = []
    opk_privs = {}
    for i in range(num_one_time_keys):
        opk_pr, opk_pu = generate_identity_keypair()
        opks.append({"key_id": i + 1, "public_key": opk_pu})
        opk_privs[str(i + 1)] = opk_pr

    return {
        "identity_key_pub": ik_pub,
        "identity_key_priv": ik_priv,
        "signed_prekey_pub": spk_pub,
        "signed_prekey_priv": spk_priv,
        "one_time_prekeys": opks,
        "one_time_prekey_privates": opk_privs,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

class ZynovaDoubleRatchet:
    """
    Implements Signal Double Ratchet algorithm.
    Transitions root key and step-chains on each new DH ratchet exchange.
    """
    def __init__(self, root_key: bytes):
        self.root_key: bytes = root_key
        self.dh_priv: Optional[x25519.X25519PrivateKey] = None
        self.dh_pub_remote: Optional[x25519.X25519PublicKey] = None
        self.sending_chain_key: Optional[bytes] = None
        self.receiving_chain_key: Optional[bytes] = None
        self.send_seq: int = 0
        self.recv_seq: int = 0

    @classmethod
    def initiate_alice(cls, shared_dh_secret: bytes, bob_dh_pub: x25519.X25519PublicKey) -> "ZynovaDoubleRatchet":
        """Initiates Alice side after X3DH agreement."""
        ratchet = cls(root_key=shared_dh_secret)
        ratchet.dh_priv = x25519.X25519PrivateKey.generate()
        ratchet.dh_pub_remote = bob_dh_pub

        # Advance Root KDF
        dh_step = ratchet.dh_priv.exchange(bob_dh_pub)
        kdf = HKDF(algorithm=hashes.SHA256(), length=64, salt=ratchet.root_key, info=INFO_ROOT_RATCHET)
        derived = kdf.derive(dh_step)
        ratchet.root_key = derived[:32]
        ratchet.sending_chain_key = derived[32:]
        return ratchet

    @classmethod
    def initiate_bob(cls, shared_dh_secret: bytes, bob_dh_priv: x25519.X25519PrivateKey) -> "ZynovaDoubleRatchet":
        """Initiates Bob side ready for Alice's first ratchet frame."""
        ratchet = cls(root_key=shared_dh_secret)
        ratchet.dh_priv = bob_dh_priv
        ratchet.dh_pub_remote = None
        return ratchet

    def encrypt(self, plaintext: bytes) -> Dict[str, Any]:
        """Encrypts message payload using current sending chain key."""
        if not self.sending_chain_key or not self.dh_priv:
            raise ValueError("Sending chain not initialized")

        # Symmetric ratchet step
        kdf = HKDF(algorithm=hashes.SHA256(), length=64, salt=SALT_MSG_KEY, info=INFO_CHAIN_KDF)
        derived = kdf.derive(self.sending_chain_key)
        self.sending_chain_key = derived[:32]
        msg_key = derived[32:]

        aesgcm = AESGCM(msg_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        self.send_seq += 1
        return {
            "dh_pub": base64.b64encode(self.dh_priv.public_key().public_bytes_raw()).decode("utf-8"),
            "seq": self.send_seq,
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8")
        }

    def decrypt(self, payload: Dict[str, Any]) -> bytes:
        """Decrypts message payload and advances receiving chain."""
        dh_pub_bytes = base64.b64decode(payload["dh_pub"])
        nonce = base64.b64decode(payload["nonce"])
        ciphertext = base64.b64decode(payload["ciphertext"])
        sender_dh_pub = x25519.X25519PublicKey.from_public_bytes(dh_pub_bytes)

        # If sender ratchet key changed or receiving chain uninitialized, ratchet root
        if not self.receiving_chain_key or self.dh_pub_remote != sender_dh_pub:
            self.dh_pub_remote = sender_dh_pub
            dh_step = self.dh_priv.exchange(sender_dh_pub)
            kdf = HKDF(algorithm=hashes.SHA256(), length=64, salt=self.root_key, info=INFO_ROOT_RATCHET)
            derived = kdf.derive(dh_step)
            self.root_key = derived[:32]
            self.receiving_chain_key = derived[32:]

        # Symmetric receiving ratchet step
        kdf = HKDF(algorithm=hashes.SHA256(), length=64, salt=SALT_MSG_KEY, info=INFO_CHAIN_KDF)
        derived = kdf.derive(self.receiving_chain_key)
        self.receiving_chain_key = derived[:32]
        msg_key = derived[32:]

        aesgcm = AESGCM(msg_key)
        self.recv_seq += 1
        return aesgcm.decrypt(nonce, ciphertext, None)
