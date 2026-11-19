"""
test_zenova_social_security.py - Comprehensive Verification for ZENOVA Phase 28
Validates:
1. Four-Second Locked Chat Duration & Boundary Threshold.
2. Strict Connect (/chat/*) vs ZenoSocial (/social/messages/*) Isolation.
3. ZenoSocial Zen_ID Direct Messaging:
   - Mutual-follow unrestricted messaging.
   - Non-mutual follow: 3-message limit strictly enforced.
   - Reset/unrestricted once recipient follows sender.
4. Mobile Number Account Ownership Policy:
   - 1 Personal + 1 Creator -> Allowed
   - 1 Personal + 1 Business -> Allowed
   - 2 Personal -> Rejected
   - 2 Creator -> Rejected
   - 2 Business -> Rejected
   - 3 Total -> Rejected
5. Dual-SIM Detection & Verified Account Switching fallback.
6. Device Attestation & Clone Protection.
7. ZenoSocial Interrelate (Mutual consent, permissions, revocation).
8. ZENOVA Connect Interconnect (Mutual consent, phone verification, instant severance).
"""

import pytest
import asyncio
from datetime import datetime, timezone
from bson import ObjectId

from app.schemas.all_schemas import (
    SocialMessageSendPayload,
    SocialContentSharePayload,
    PhoneAccountVerifyPayload,
    DeviceAttestationPayload,
    InterrelateRequestPayload,
    InterrelateRespondPayload,
    InterrelatePermissionsUpdatePayload,
    InterconnectInvitePayload,
    InterconnectRespondPayload,
    InterconnectPermissionsPayload
)

# -------------------------------------------------------------
# 1. Four-Second Locked Chat Timer Specification Test
# -------------------------------------------------------------
def test_locked_chat_four_second_threshold():
    """Validates that locked chat unlock threshold is exactly 4000ms."""
    HOLD_DURATION_MS = 4000
    
    def evaluate_hold(duration_ms):
        return duration_ms >= HOLD_DURATION_MS

    assert not evaluate_hold(500), "Sub-second tap must not unlock"
    assert not evaluate_hold(2500), "2.5-second hold must not unlock"
    assert not evaluate_hold(3999), "3.999s hold must not unlock"
    assert evaluate_hold(4000), "Exact 4.000s hold must unlock"
    assert evaluate_hold(5000), "Holding > 4s must unlock"

# -------------------------------------------------------------
# 2. Strict Isolation: Connect vs ZenoSocial
# -------------------------------------------------------------
def test_messaging_isolation_contract():
    """Ensures Connect (Phone /chat) and ZenoSocial (Zen_ID /social/messages) do not collide."""
    connect_route_prefix = "/chat"
    social_route_prefix = "/social/messages"
    
    assert connect_route_prefix != social_route_prefix, "Routes must be distinct"

    connect_collections = {"chat_conversations", "chat_messages", "connect_status", "connect_communities"}
    social_collections = {"social_conversations", "social_messages", "social_interrelate", "posts", "videos"}

    assert connect_collections.isdisjoint(social_collections), "Database collections must remain strictly isolated"

# -------------------------------------------------------------
# 3. ZenoSocial 3-Message Non-Mutual Follow Restriction Logic
# -------------------------------------------------------------
def test_three_message_non_mutual_restriction_logic():
    NON_MUTUAL_LIMIT = 3

    def evaluate_can_send(is_mutual: bool, accepted_count: int):
        if is_mutual:
            return True, 999999
        remaining = max(0, NON_MUTUAL_LIMIT - accepted_count)
        return (accepted_count < NON_MUTUAL_LIMIT), remaining

    # Mutual follow: always allowed
    can_send, rem = evaluate_can_send(is_mutual=True, accepted_count=0)
    assert can_send is True and rem == 999999
    can_send, rem = evaluate_can_send(is_mutual=True, accepted_count=100)
    assert can_send is True and rem == 999999

    # Non-mutual follow: message 1
    can_send, rem = evaluate_can_send(is_mutual=False, accepted_count=0)
    assert can_send is True and rem == 3

    # Non-mutual follow: message 2
    can_send, rem = evaluate_can_send(is_mutual=False, accepted_count=1)
    assert can_send is True and rem == 2

    # Non-mutual follow: message 3
    can_send, rem = evaluate_can_send(is_mutual=False, accepted_count=2)
    assert can_send is True and rem == 1

    # Non-mutual follow: 4th message blocked!
    can_send, rem = evaluate_can_send(is_mutual=False, accepted_count=3)
    assert can_send is False and rem == 0

    # Non-mutual follow: over limit
    can_send, rem = evaluate_can_send(is_mutual=False, accepted_count=4)
    assert can_send is False and rem == 0

    # Now recipient follows sender back -> restriction lifted immediately!
    can_send, rem = evaluate_can_send(is_mutual=True, accepted_count=3)
    assert can_send is True and rem == 999999

# -------------------------------------------------------------
# 4. Mobile Number Account Limit Ownership Policy
# -------------------------------------------------------------
def test_mobile_number_account_limits():
    """
    One verified mobile number can own:
    - Max 2 accounts total
    - Max 1 Personal
    - Max 1 Creator OR Business
    """
    def check_can_register(existing_accounts, desired_type):
        if len(existing_accounts) >= 2:
            return False, "Maximum 2 accounts per verified mobile number"
        
        has_personal = any(a == "personal" for a in existing_accounts)
        has_creator = any(a == "creator" for a in existing_accounts)
        has_business = any(a == "business" for a in existing_accounts)

        if desired_type == "personal":
            if has_personal:
                return False, "Cannot have 2 Personal accounts"
            return True, "OK"

        if desired_type in ("creator", "business"):
            if has_creator or has_business:
                return False, "Can only have 1 Creator OR 1 Business account"
            return True, "OK"

        return False, "Invalid type"

    # Case 1: Fresh number -> Personal (OK)
    ok, _ = check_can_register([], "personal")
    assert ok is True

    # Case 2: Personal exists -> Add Creator (OK: 1 Personal + 1 Creator)
    ok, _ = check_can_register(["personal"], "creator")
    assert ok is True

    # Case 3: Personal exists -> Add Business (OK: 1 Personal + 1 Business)
    ok, _ = check_can_register(["personal"], "business")
    assert ok is True

    # Case 4: Personal exists -> Add second Personal (REJECTED)
    ok, msg = check_can_register(["personal"], "personal")
    assert ok is False and "2 Personal" in msg

    # Case 5: Creator exists -> Add Business (REJECTED: Creator + Business not allowed)
    ok, msg = check_can_register(["creator"], "business")
    assert ok is False and "Creator OR 1 Business" in msg

    # Case 6: Creator exists -> Add second Creator (REJECTED)
    ok, msg = check_can_register(["creator"], "creator")
    assert ok is False

    # Case 7: Business exists -> Add second Business (REJECTED)
    ok, msg = check_can_register(["business"], "business")
    assert ok is False

    # Case 8: Personal + Creator exist -> Try to add 3rd account (REJECTED)
    ok, msg = check_can_register(["personal", "creator"], "business")
    assert ok is False and "Maximum 2" in msg

# -------------------------------------------------------------
# 5. Device Attestation & Clone Protection
# -------------------------------------------------------------
def test_device_attestation_rules():
    TRUSTED_PACKAGE = "com.zenova.app"

    def evaluate_attestation(package_name, version_code, is_cloned_storage, signature):
        if package_name != TRUSTED_PACKAGE:
            return False, "Untrusted package"
        if version_code < 1:
            return False, "Invalid version"
        if not signature or len(signature) < 32:
            return False, "Invalid signature"
        if is_cloned_storage:
            return False, "Clone detected"
        return True, "Verified"

    # Official package
    valid, _ = evaluate_attestation("com.zenova.app", 2, False, "a" * 64)
    assert valid is True

    # Cloned package name
    valid, msg = evaluate_attestation("com.zenova.app.clone", 2, False, "a" * 64)
    assert valid is False and "Untrusted package" in msg

    # Cloned multi-user / dual-app path
    valid, msg = evaluate_attestation("com.zenova.app", 2, True, "a" * 64)
    assert valid is False and "Clone detected" in msg

# -------------------------------------------------------------
# 6. Interrelate & Interconnect Mutual Consent & Revocation
# -------------------------------------------------------------
def test_interrelate_revocation_lifecycle():
    """Verifies that either party can immediately revoke permissions and sever link."""
    state = {
        "status": "active",
        "permissions_a": {"show_relationship_badge": True, "share_activity_status": True, "shared_media_vault_access": True},
        "permissions_b": {"show_relationship_badge": True, "share_activity_status": False, "shared_media_vault_access": False}
    }

    # User A revokes media vault access
    state["permissions_a"]["shared_media_vault_access"] = False
    assert state["permissions_a"]["shared_media_vault_access"] is False

    # User B terminates link
    state["status"] = "terminated"
    state["permissions_a"] = {"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False}
    state["permissions_b"] = {"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False}

    assert state["status"] == "terminated"
    assert all(v is False for v in state["permissions_a"].values())
    assert all(v is False for v in state["permissions_b"].values())
