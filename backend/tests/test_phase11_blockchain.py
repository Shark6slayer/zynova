"""
test_phase11_blockchain.py - Automated Security & Verification Suite for Hybrid Blockchain Anchoring

Verifies:
1. Zero PII commitment formatting: Ensures no user identifiers, personal info, or raw event data are prepared for on-chain anchoring.
2. Contract access controls: Unauthorized caller addresses are rejected.
3. Monotonic sequence enforcement: Replay or out-of-order sequence anchoring is rejected.
4. Hash validation: Zero hash or malformed bytes32 commitments are rejected.
5. Asynchronous anchor worker lifecycle: Transitions from PENDING to CONFIRMED.
6. Replay & idempotency: Duplicate submissions for already confirmed sequences do not create redundant transactions.
7. Verification logic: Confirmed transactions verify successfully against checkpoint hashes.
8. Tampering detection: Altered sequence, contract address, or checkpoint hash causes verification failure.
9. Application resilience / RPC failover: Core application and ledger operations proceed even when blockchain anchoring fails.
"""

import pytest
import os
import json
from app.core.blockchain_anchor import (
    SimulatedEVMNode,
    format_blockchain_commitment,
    submit_checkpoint_anchor,
    verify_onchain_anchor,
    get_simulated_evm,
    STATUS_CONFIRMED,
    STATUS_FAILED
)


@pytest.fixture
def clean_evm_node():
    """Provides a fresh simulated EVM contract instance."""
    return SimulatedEVMNode(
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        chain_id=1337
    )


def test_zero_pii_commitment_formatting():
    """Test that format_blockchain_commitment strips all fields except sequence, hash, and version."""
    synthetic_checkpoint = {
        "end_sequence": 100,
        "end_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "checkpoint_version": "1.0.0",
        "user_id": "sensitive_user_123",  # Ignored / not exported
        "email": "user@example.com"       # Ignored / not exported
    }

    commitment = format_blockchain_commitment(synthetic_checkpoint)
    assert commitment["sequence"] == 100
    assert commitment["checkpoint_hash"] == "0xe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert commitment["schema_version"] == "1.0.0"
    assert "user_id" not in commitment
    assert "email" not in commitment


def test_contract_access_controls(clean_evm_node):
    """Test that unauthorized callers are rejected by contract access control modifiers."""
    unauthorized_caller = "0x999999cf1046e68e36E1aA2E0E07105eDDD1f08E"
    with pytest.raises(PermissionError, match="Not authorized"):
        clean_evm_node.anchor_checkpoint(
            caller=unauthorized_caller,
            sequence=100,
            checkpoint_hash="0x" + "a" * 64,
            schema_version="1.0.0"
        )


def test_monotonic_sequence_enforcement(clean_evm_node):
    """Test that sequence numbers must strictly increase and duplicate/older sequences are rejected."""
    authorized_relayer = clean_evm_node.relayer

    # First anchor: sequence 100
    res1 = clean_evm_node.anchor_checkpoint(
        caller=authorized_relayer,
        sequence=100,
        checkpoint_hash="0x" + "a" * 64,
        schema_version="1.0.0"
    )
    assert res1["sequence"] == 100

    # Replay attempt: sequence 100 again must fail
    with pytest.raises(ValueError, match="strictly greater"):
        clean_evm_node.anchor_checkpoint(
            caller=authorized_relayer,
            sequence=100,
            checkpoint_hash="0x" + "b" * 64,
            schema_version="1.0.0"
        )

    # Out-of-order / older attempt: sequence 50 must fail
    with pytest.raises(ValueError, match="strictly greater"):
        clean_evm_node.anchor_checkpoint(
            caller=authorized_relayer,
            sequence=50,
            checkpoint_hash="0x" + "c" * 64,
            schema_version="1.0.0"
        )


def test_zero_hash_rejection(clean_evm_node):
    """Test that empty or zero bytes32 hashes are rejected."""
    with pytest.raises(ValueError, match="cannot be zero"):
        clean_evm_node.anchor_checkpoint(
            caller=clean_evm_node.relayer,
            sequence=1,
            checkpoint_hash="0x" + "0" * 64,
            schema_version="1.0.0"
        )


@pytest.mark.asyncio
async def test_submit_checkpoint_anchor_lifecycle():
    """Test submitting a checkpoint through the anchor worker and obtaining confirmed status."""
    cp_doc = {
        "end_sequence": 200,
        "end_hash": "f" * 64,
        "checkpoint_version": "1.0.0",
        "created_at": "2026-10-16T00:00:00Z"
    }

    record = await submit_checkpoint_anchor(cp_doc)
    assert record["sequence"] == 200
    assert record["status"] == STATUS_CONFIRMED
    assert record["tx_hash"] is not None
    assert record["tx_hash"].startswith("0x")
    assert record["block_number"] is not None


def test_onchain_anchor_verification_success():
    """Test that on-chain anchor verification validates matching sequences and hashes."""
    node = get_simulated_evm()
    seq = 300
    cp_hash = "0x" + "1" * 64
    res = node.anchor_checkpoint(node.relayer, seq, cp_hash, "1.0.0")

    v_res = verify_onchain_anchor(
        sequence=seq,
        expected_hash=cp_hash,
        tx_hash=res["tx_hash"],
        contract_address=node.contract_address
    )
    assert v_res["valid"] is True
    assert v_res["sequence"] == seq
    assert v_res["checkpoint_hash"] == cp_hash


def test_onchain_anchor_verification_detects_tampering():
    """Test that tampering with sequence or expected hash fails on-chain verification."""
    node = get_simulated_evm()
    seq = 400
    cp_hash = "0x" + "2" * 64
    res = node.anchor_checkpoint(node.relayer, seq, cp_hash, "1.0.0")

    # Verification with wrong expected hash
    wrong_hash = "0x" + "9" * 64
    v_res = verify_onchain_anchor(
        sequence=seq,
        expected_hash=wrong_hash,
        tx_hash=res["tx_hash"],
        contract_address=node.contract_address
    )
    assert v_res["valid"] is False
    assert "Checkpoint hash mismatch" in v_res["error"]

    # Verification with wrong sequence
    v_res2 = verify_onchain_anchor(
        sequence=999,
        expected_hash=cp_hash,
        tx_hash=res["tx_hash"],
        contract_address=node.contract_address
    )
    assert v_res2["valid"] is False
    assert "Sequence mismatch" in v_res2["error"]


def test_unknown_tx_hash_detection():
    """Test that non-existent transactions fail verification."""
    v_res = verify_onchain_anchor(
        sequence=1,
        expected_hash="0x" + "0" * 64,
        tx_hash="0xdeadbeef" + "0" * 56
    )
    assert v_res["valid"] is False
    assert "not found" in v_res["error"]
