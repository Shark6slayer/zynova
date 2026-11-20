import asyncio
import os
import sys
from email.utils import make_msgid
from app.core.config import settings
from app.services.email_service import EmailService

async def main():
    test_email = os.environ.get('TEST_EMAIL')
    if not test_email:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('TEST_EMAIL='):
                    test_email = line.split('=', 1)[1].strip()
                    break

    if not test_email:
        print('ERROR: TEST_EMAIL not found in .env')
        sys.exit(1)

    subject = 'SUPER_AI - SMTP Delivery Test'
    msg_id = make_msgid(domain='intellidev.in')
    
    masked_email = f"{test_email[:3]}***@{test_email.split('@')[-1]}"
    print(f"DISPATCHING_TO: {masked_email}")

    html_body = f"""<!DOCTYPE html>
<html>
<body style="background-color:#0b0f19;color:#ffffff;font-family:sans-serif;padding:30px;">
  <div style="max-width:500px;margin:auto;background:#111827;padding:30px;border-radius:12px;border:1px solid #374151;">
    <h2 style="color:#8b5cf6;">SUPER_AI - Phase 2 SMTP Verification</h2>
    <p>This is a live transactional delivery test sent from <strong>no-reply@intellidev.in</strong> via GoDaddy Titan SMTP (smtpout.secureserver.net:465 SSL).</p>
    <p style="background:#1f2937;padding:12px;border-radius:8px;font-family:monospace;font-size:12px;color:#9ca3af;">Message-ID: {msg_id}</p>
    <p style="color:#10b981;">SMTP SSL handshake and authentication verified.</p>
  </div>
</body>
</html>"""

    text_body = f"SUPER_AI - SMTP Delivery Test\n\nLive transactional email delivery test from no-reply@intellidev.in via GoDaddy Titan SMTP.\nMessage-ID: {msg_id}\n"

    try:
        ok = await EmailService.send_email(
            to_email=test_email,
            subject=subject,
            html_content=html_body,
            text_content=text_body
        )
        print(f"DELIVERY_ACCEPTED: {ok}")
        print(f"MESSAGE_ID: {msg_id}")
    except Exception as e:
        print(f"DELIVERY_FAILED: {type(e).__name__} - {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
