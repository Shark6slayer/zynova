"""
ZENOVA — Zoho Catalyst Mail Delivery Diagnostic Tool
Safely checks configuration presence, tests OAuth token exchange, and verifies email dispatch.
CRITICAL: Never logs or prints raw secrets, passwords, or tokens.
"""

import sys
import os
import asyncio
from pathlib import Path

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
# Load local .env if available
load_dotenv(backend_dir / ".env")

from app.core.config import settings
from app.services.catalyst_mail_service import (
    CatalystMailService,
    CatalystOAuthException,
    CatalystDeliveryException
)

def mask_val(val: str) -> str:
    if not val:
        return "<MISSING / NOT SET>"
    if len(val) <= 6:
        return "***"
    return f"{val[:3]}...{val[-3:]} (len {len(val)})"

async def run_diagnostics(target_recipient: str = "karuppusamyc80@gmail.com"):
    print("=" * 60)
    print("ZENOVA ZOHO CATALYST MAIL DELIVERY DIAGNOSTIC AUDIT")
    print("=" * 60)

    # 1. Environment & Variable Inspection
    print("\n[1/4] Inspecting Catalyst Configuration Variables:")
    vars_to_check = [
        ("EMAIL_PROVIDER", settings.EMAIL_PROVIDER),
        ("ENVIRONMENT", settings.ENVIRONMENT),
        ("CATALYST_PROJECT_ID", settings.CATALYST_PROJECT_ID),
        ("CATALYST_FROM_EMAIL", settings.CATALYST_FROM_EMAIL),
        ("CATALYST_DISPLAY_NAME", settings.effective_catalyst_display_name),
        ("CATALYST_ENVIRONMENT", settings.CATALYST_ENVIRONMENT),
        ("CATALYST_ACCOUNTS_URL", settings.effective_catalyst_accounts_url),
        ("CATALYST_API_DOMAIN", settings.effective_catalyst_api_domain),
        ("CATALYST_CLIENT_ID / ZOHO_CLIENT_ID", settings.effective_catalyst_client_id),
        ("CATALYST_CLIENT_SECRET / ZOHO_CLIENT_SECRET", settings.effective_catalyst_client_secret),
        ("CATALYST_REFRESH_TOKEN / ZOHO_REFRESH_TOKEN", settings.effective_catalyst_refresh_token),
        ("OTP_HASH_SECRET", settings.OTP_HASH_SECRET or "<Falls back to JWT_SECRET_KEY>"),
    ]

    missing = []
    for name, val in vars_to_check:
        masked = mask_val(val) if "SECRET" in name or "TOKEN" in name or "CLIENT_ID" in name else (val or "<MISSING>")
        status = "✓ PRESENT" if val else "✗ MISSING"
        if not val:
            missing.append(name)
        print(f"  - {name:<45} : {masked} [{status}]")

    is_ready = CatalystMailService.is_configured()
    print(f"\nConfiguration Status: {'READY' if is_ready else 'INCOMPLETE (Credentials Missing)'}")

    if not is_ready:
        print("\n[!] FATAL CONFIGURATION DEFICIT:")
        print(f"    Missing critical variables: {', '.join(missing)}")
        print("    Email dispatch cannot proceed without valid Zoho Catalyst OAuth credentials.")
        return False

    # 2. OAuth 2.0 Token Refresh Test
    print("\n[2/4] Testing OAuth 2.0 Token Exchange:")
    print(f"  Target Token Endpoint: {settings.effective_catalyst_accounts_url.rstrip('/')}/oauth/v2/token")
    try:
        token = await CatalystMailService.get_access_token()
        print("  ✓ OAuth Access Token successfully acquired and cached.")
        print(f"  Token length: {len(token)} characters | Cached until: {CatalystMailService._token_expires_at}")
    except CatalystOAuthException as e:
        print(f"  ✗ OAuth Token Refresh Failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error during OAuth token exchange: {e}")
        return False

    # 3. Controlled Live Test Dispatch
    print(f"\n[3/4] Performing Controlled Live Test Dispatch to: {target_recipient}")
    subject = "ZENOVA — Catalyst Mail Delivery Diagnostic Test"
    html = f"""
    <div style="font-family: sans-serif; background-color: #0b0f19; color: #f3f4f6; padding: 24px; border-radius: 8px;">
      <h2 style="color: #8b5cf6;">ZENOVA Sovereign Delivery Verification</h2>
      <p>This is a controlled diagnostic delivery verification sent via Zoho Catalyst Cloud Scale Mail.</p>
      <p><strong>Project ID:</strong> {settings.CATALYST_PROJECT_ID}</p>
      <p><strong>Sender:</strong> {settings.CATALYST_FROM_EMAIL}</p>
      <p><strong>Environment:</strong> {settings.CATALYST_ENVIRONMENT}</p>
    </div>
    """
    try:
        resp = await CatalystMailService.send_email(
            to_email=target_recipient,
            subject=subject,
            html_content=html,
            text_content="ZENOVA diagnostic email delivery test."
        )
        print("  ✓ Catalyst Mail API accepted delivery request.")
        print(f"  Response: {resp}")
        print("\n[4/4] Delivery Validation Result: SUCCESS")
        print(f"  An email has been dispatched to {target_recipient}.")
        print("  Please check inbox and spam folders to confirm physical delivery and sender identity.")
        return True
    except CatalystDeliveryException as e:
        print(f"  ✗ Catalyst Mail Delivery API Rejected Request: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected delivery error: {e}")
        return False

if __name__ == "__main__":
    recipient = sys.argv[1] if len(sys.argv) > 1 else "karuppusamyc80@gmail.com"
    asyncio.run(run_diagnostics(recipient))
