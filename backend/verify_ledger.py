"""
verify_ledger.py - Standalone Independent Cryptographic Audit Ledger Verifier

Can be run offline or as a CLI tool against an exported JSON ledger file
or connected directly to the application database:

Usage:
  python verify_ledger.py --file export.json
  python verify_ledger.py --db
"""

import sys
import json
import argparse
from typing import List, Dict, Any
from app.core.audit_ledger import (
    verify_ledger_records,
    verify_checkpoint_signature,
    canonical_json_dumps
)

def verify_file(filepath: str) -> bool:
    print(f"[*] Reading audit ledger records from '{filepath}'...")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] Failed to read file: {e}")
        return False

    records = data if isinstance(data, list) else data.get("records", [])
    checkpoints = data.get("checkpoints", []) if isinstance(data, dict) else []

    print(f"[*] Verifying {len(records)} ledger records...")
    res = verify_ledger_records(records)

    if not res["valid"]:
        print(f"\n[FAIL] LEDGER VERIFICATION FAILED with {len(res['errors'])} error(s):")
        for err in res["errors"]:
            print(f"  - {err}")
        return False

    print(f"\n[PASS] Ledger chain is valid! Verified {res['count']} events.")
    print(f"  Sequence range: {res.get('first_sequence')} -> {res.get('last_sequence')}")
    print(f"  Genesis hash link: {records[0].get('prev_hash')[:16]}...")
    print(f"  Latest head hash: {res.get('last_hash')[:16]}...")

    if checkpoints:
        print(f"\n[*] Verifying {len(checkpoints)} signed checkpoint(s)...")
        cp_errors = []
        for idx, cp in enumerate(checkpoints):
            sig = cp.get("signature")
            pub_key = cp.get("public_key")
            cp_body = {
                "checkpoint_version": cp.get("checkpoint_version"),
                "end_hash": cp.get("end_hash"),
                "end_sequence": cp.get("end_sequence"),
                "public_key": pub_key,
                "timestamp": cp.get("timestamp"),
            }
            canonical_cp = canonical_json_dumps(cp_body)
            if not verify_checkpoint_signature(canonical_cp, sig, pub_key):
                cp_errors.append(f"Invalid Ed25519 signature on checkpoint {idx} (end_seq={cp.get('end_sequence')})")

        if cp_errors:
            print(f"[FAIL] CHECKPOINT VERIFICATION FAILED:")
            for e in cp_errors:
                print(f"  - {e}")
            return False
        else:
            print(f"[PASS] All {len(checkpoints)} checkpoint signature(s) verified successfully!")

    # Phase 11: Blockchain Anchoring Verification
    anchors = data.get("blockchain_anchors", []) if isinstance(data, dict) else []
    if anchors:
        print(f"\n[*] Verifying {len(anchors)} blockchain anchor commitment(s)...")
        from app.core.blockchain_anchor import verify_onchain_anchor
        anchor_errors = []
        for idx, anc in enumerate(anchors):
            seq = anc.get("sequence")
            cp_hash = anc.get("checkpoint_hash")
            tx_hash = anc.get("tx_hash")
            contract_addr = anc.get("contract_address")

            if not tx_hash:
                anchor_errors.append(f"Anchor {idx} for seq={seq} has no tx_hash recorded")
                continue

            v_res = verify_onchain_anchor(seq, cp_hash, tx_hash, contract_addr)
            if not v_res["valid"]:
                anchor_errors.append(f"On-chain anchor verification failed for seq={seq}: {v_res.get('error')}")

        if anchor_errors:
            print(f"[FAIL] BLOCKCHAIN ANCHOR VERIFICATION FAILED:")
            for e in anchor_errors:
                print(f"  - {e}")
            return False
        else:
            print(f"[PASS] All {len(anchors)} on-chain anchor commitment(s) verified successfully!")

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SUPER_AI Independent Ledger & Blockchain Anchor Verifier")
    parser.add_argument("--file", type=str, help="Path to exported ledger JSON file")
    args = parser.parse_args()

    if not args.file:
        print("Usage: python verify_ledger.py --file <path_to_export.json>")
        sys.exit(1)

    success = verify_file(args.file)
    sys.exit(0 if success else 1)
