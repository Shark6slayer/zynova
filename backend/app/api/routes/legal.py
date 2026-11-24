"""
SUPER_AI / ZENOVA — Legal & Regulatory Compliance Endpoints
Serves authoritative, responsive, DPDP/GDPR-compliant Privacy Policy,
Apple Guideline 1.2 compliant Terms of Service, and web account deletion portal.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/legal", tags=["Legal & Regulatory Compliance"])

SHARED_CSS = """
<style>
    :root {
        --bg: #090A0F;
        --card-bg: #12141D;
        --border: #232838;
        --primary: #7C4DFF;
        --primary-hover: #9E75FF;
        --text: #F0F2F8;
        --muted: #9BA3AF;
        --danger: #FF5252;
        --success: #00E676;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: var(--bg);
        color: var(--text);
        line-height: 1.6;
        padding: 40px 20px;
    }
    .container {
        max-width: 860px;
        margin: 0 auto;
        background-color: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 40px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    h1 {
        font-size: 2rem;
        color: #FFFFFF;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .badge {
        font-size: 0.75rem;
        font-weight: 600;
        background: var(--primary);
        color: #fff;
        padding: 4px 10px;
        border-radius: 999px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .subtitle {
        color: var(--muted);
        margin-bottom: 30px;
        font-size: 0.95rem;
        border-bottom: 1px solid var(--border);
        padding-bottom: 16px;
    }
    h2 {
        font-size: 1.3rem;
        color: var(--primary-hover);
        margin-top: 32px;
        margin-bottom: 12px;
    }
    h3 {
        font-size: 1.05rem;
        color: #E2E8F0;
        margin-top: 20px;
        margin-bottom: 8px;
    }
    p, li {
        color: var(--muted);
        font-size: 0.95rem;
        margin-bottom: 12px;
    }
    ul, ol {
        margin-left: 24px;
        margin-bottom: 16px;
    }
    li { margin-bottom: 6px; }
    strong { color: var(--text); }
    .alert-box {
        background: rgba(124, 77, 255, 0.08);
        border: 1px solid rgba(124, 77, 255, 0.25);
        border-radius: 8px;
        padding: 16px;
        margin: 20px 0;
    }
    .danger-box {
        background: rgba(255, 82, 82, 0.08);
        border: 1px solid rgba(255, 82, 82, 0.25);
        border-radius: 8px;
        padding: 16px;
        margin: 20px 0;
    }
    .footer {
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid var(--border);
        font-size: 0.85rem;
        color: var(--muted);
        text-align: center;
    }
    a { color: var(--primary-hover); text-decoration: none; }
    a:hover { text-decoration: underline; }
    @media (max-width: 640px) {
        .container { padding: 24px 18px; }
        h1 { font-size: 1.6rem; }
    }
</style>
"""

PRIVACY_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZENOVA — Sovereign Privacy Policy</title>
    {SHARED_CSS}
</head>
<body>
    <div class="container">
        <h1>ZENOVA <span class="badge">Privacy Policy</span></h1>
        <div class="subtitle">Effective Date: November 24, 2026 | In accordance with Apple Guideline 5.1, Google Play User Data Policy, and India DPDP Act 2023</div>

        <h2>1. Overview & Sovereign Privacy Commitment</h2>
        <p>ZENOVA ("we", "our", or "the Platform") is engineered as a sovereign digital ecosystem providing unified social communication, decentralized video discovery, and utility management. We operate under strict data minimization principles: we collect only data necessary to deliver authenticated services, do not sell user data to data brokers, and do not track users across third-party websites or applications.</p>

        <h2>2. Information We Collect</h2>
        <p>We collect and process the following categories of data solely for app functionality:</p>
        <ul>
            <li><strong>Identity & Account Details:</strong> Full name, email address, password hash (Argon2id), and chosen sovereign username (Zen_ID e.g. <code>@username</code>).</li>
            <li><strong>User-Generated Content:</strong> Profile photos, ZenoSocial posts, video stories, comments, and Connect messages initiated by you.</li>
            <li><strong>Audio Recordings:</strong> Voice notes and audio messages recorded explicitly via microphone with your in-app consent.</li>
            <li><strong>Financial & Payment Identifiers:</strong> Masked bank account numbers (retaining only the last 4 digits), user UPI handles, and retrieval reference numbers (RRN) for payment verification. Full account numbers and PINs are never stored on our servers.</li>
            <li><strong>Device & Session Tokens:</strong> Push notification tokens, cryptographic device session identifiers, and IP addresses (used exclusively for rate limiting and fraud prevention).</li>
        </ul>

        <h2>3. Zero Third-Party Cross-App Tracking</h2>
        <div class="alert-box">
            <strong>Apple App Store & Privacy Manifest Declaration:</strong> ZENOVA declares <code>NSPrivacyTracking = false</code> and maintains an empty tracking domain list (<code>NSPrivacyTrackingDomains = []</code>). We do not collect Apple Identifier for Advertisers (IDFA) or share tracking profiles with external data brokers.
        </div>

        <h2>4. Data Storage, Security & Encryption</h2>
        <ul>
            <li><strong>In Transit:</strong> All communication between client applications (iOS, Android, Web) and our servers is strictly encrypted using TLS 1.3 / HTTPS. Cleartext traffic is disallowed.</li>
            <li><strong>Password Security:</strong> Passwords are hashed using the memory-hard Argon2id cryptographic algorithm. Plaintext passwords are never logged or stored.</li>
            <li><strong>Verification Codes:</strong> 6-digit email verification and recovery codes are hashed using HMAC-SHA256, enforced with single-use consumption and automatic 5-minute expiration.</li>
            <li><strong>Media Storage:</strong> User media files (photos, videos, audio notes) are stored in secure S3-compatible cloud storage with restricted access permissions.</li>
        </ul>

        <h2>5. 30-Day Account Deletion & Recovery Protocol</h2>
        <p>In full compliance with Apple Guideline 5.1.1(v) and Google Play Account Deletion mandates, ZENOVA provides a complete, durable account deletion lifecycle:</p>
        <ol>
            <li><strong>Initiation:</strong> You can initiate account deletion at any time in-app via <em>Settings &rarr; Sovereign Privacy Hub &rarr; Delete Sovereign Account</em>, requiring password verification.</li>
            <li><strong>Immediate Session Revocation:</strong> Upon request, all active JWT access tokens, refresh tokens, and device sessions are immediately revoked. Your profile and content become completely hidden from other users.</li>
            <li><strong>30-Day Recovery Grace Period:</strong> You retain the sovereign right to cancel the deletion and restore full access within 30 days by verifying a 6-digit OTP sent to your registered email.</li>
            <li><strong>Permanent Cascading Erasure:</strong> On Day 30, our automated background worker permanently and irreversibly purges your account record, social posts, comments, followers, Connect chats, video views, shopping carts, and external media storage assets.</li>
        </ol>

        <h2>6. Web-Based Account Deletion Link</h2>
        <p>If you have uninstalled the application or cannot access your device, you may submit an off-app deletion request via our verified web portal at <a href="/delete-account">https://api.zenova.intellidev.in/delete-account</a>.</p>

        <h2>7. Contact Information & Data Protection Officer</h2>
        <p>For inquiries regarding this Privacy Policy, data access requests, or regulatory questions, contact our Data Protection Office at: <a href="mailto:privacy@intellidev.in">privacy@intellidev.in</a>.</p>

        <div class="footer">
            &copy; 2026 ZENOVA Ecosystem &bull; IntelliDev Sovereign Technologies &bull; All Rights Reserved.
        </div>
    </div>
</body>
</html>
"""

TERMS_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZENOVA — Terms of Service & EULA</title>
    {SHARED_CSS}
</head>
<body>
    <div class="container">
        <h1>ZENOVA <span class="badge">Terms of Service</span></h1>
        <div class="subtitle">Effective Date: November 24, 2026 | End User License Agreement (EULA)</div>

        <h2>1. Acceptance of Terms</h2>
        <p>By creating an account, downloading, or using ZENOVA (on Android, iOS, or Web), you agree to be bound by these Terms of Service and our Privacy Policy. If you do not agree to these terms, do not create an account or use the application.</p>

        <h2>2. Sovereign Account Eligibility & Security</h2>
        <ul>
            <li>You must be at least 13 years of age (or the minimum legal age in your jurisdiction) to create an account.</li>
            <li>You are responsible for safeguarding your credentials. ZENOVA will never ask for your password or OTP.</li>
            <li>You agree to provide accurate registration information and maintain the security of your account.</li>
        </ul>

        <h2>3. Apple Guideline 1.2 — User-Generated Content (UGC) & Zero-Tolerance Policy</h2>
        <div class="danger-box">
            <strong>CRITICAL USER CONDUCT CLAUSE:</strong> ZENOVA maintains a strict <strong>ZERO-TOLERANCE POLICY</strong> for objectionable content, abusive behavior, and harassment.
        </div>
        <p>You strictly agree that you will NOT upload, post, transmit, or share content that:</p>
        <ul>
            <li>Is defamatory, obscene, pornographic, sexually explicit, or vulgar.</li>
            <li>Promotes discrimination, bigotry, racism, hatred, or physical harm against any group or individual.</li>
            <li>Harasses, bullies, stalks, threatens, or intimidates any user or minor.</li>
            <li>Depicts illegal acts, violence, self-harm, or terrorist activity.</li>
            <li>Infringes on copyright, trademark, privacy, or proprietary rights of third parties.</li>
        </ul>

        <h3>Content Moderation, Flagging & 24-Hour Enforcement</h3>
        <ul>
            <li><strong>Content Flagging:</strong> Users may flag any objectionable post, comment, or message using the in-app reporting tools.</li>
            <li><strong>User Blocking:</strong> Users may block any abusive account at any time, immediately preventing further communication or content visibility.</li>
            <li><strong>24-Hour Action Guarantee:</strong> Our safety team reviews all flagged content within 24 hours. Content violating these terms will be immediately removed, and the offending user account will be permanently banned.</li>
        </ul>

        <h2>4. Video Streaming & Third-Party Platforms</h2>
        <p>ZENOVA Play features embedded video content utilizing the official YouTube IFrame Player API. Video playback complies with YouTube Terms of Service. ZENOVA does not charge fees for viewing publicly available YouTube content.</p>

        <h2>5. Account Deletion & Termination</h2>
        <p>You may terminate your account at any time using the in-app account deletion protocol. We reserve the right to suspend or terminate accounts that violate our Zero-Tolerance UGC policy without prior notice.</p>

        <h2>6. Limitation of Liability & Governing Law</h2>
        <p>ZENOVA is provided on an "AS IS" and "AS AVAILABLE" basis. To the maximum extent permitted by law, IntelliDev and its affiliates disclaim all warranties, express or implied. These terms are governed by the laws of India, subject to the jurisdiction of the competent courts.</p>

        <div class="footer">
            &copy; 2026 ZENOVA Ecosystem &bull; IntelliDev Sovereign Technologies &bull; All Rights Reserved.
        </div>
    </div>
</body>
</html>
"""

DELETE_ACCOUNT_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZENOVA — Account & Data Deletion Portal</title>
    {SHARED_CSS}
</head>
<body>
    <div class="container">
        <h1>ZENOVA <span class="badge">Account Deletion</span></h1>
        <div class="subtitle">Google Play & Apple Compliant Account & Data Deletion Portal</div>

        <h2>Sovereign Account Deletion Information</h2>
        <p>In accordance with Google Play User Data policies and Apple App Store Review Guidelines, ZENOVA allows users to permanently delete their account and all associated personal data.</p>

        <div class="alert-box">
            <strong>How to Delete in the Mobile App (Recommended):</strong><br>
            Open <strong>ZENOVA</strong> &rarr; Navigate to <strong>Settings</strong> &rarr; Select <strong>Sovereign Privacy Hub</strong> &rarr; Tap <strong>Delete Sovereign Account</strong> &rarr; Enter your password and confirm.
        </div>

        <h2>Off-App / Web-Based Account Deletion Request</h2>
        <p>If you have uninstalled the application or cannot access your mobile device, you can request account deletion by emailing our privacy team directly from your registered email address:</p>
        <div class="alert-box" style="text-align: center;">
            <p>Send an email to: <strong><a href="mailto:privacy@intellidev.in?subject=ZENOVA%20Account%20Deletion%20Request">privacy@intellidev.in</a></strong></p>
            <p>Subject: <code>ZENOVA Account Deletion Request</code></p>
            <p>Include: Your registered email address and sovereign Zen_ID (<code>@username</code>).</p>
        </div>

        <h2>What Happens When You Delete Your Account</h2>
        <ul>
            <li><strong>Immediate Effect:</strong> All login sessions and tokens are instantly revoked. Your profile, username, posts, and chats become invisible to other users.</li>
            <li><strong>30-Day Recovery Period:</strong> You can cancel the deletion and restore your account within 30 days via email OTP verification.</li>
            <li><strong>Permanent Destruction (Day 30+):</strong> All posts, comments, media files (photos, videos, audio notes), chat logs, follower graphs, and database records are permanently deleted from all active and backup servers.</li>
        </ul>

        <div class="footer">
            &copy; 2026 ZENOVA Ecosystem &bull; IntelliDev Sovereign Technologies &bull; All Rights Reserved.
        </div>
    </div>
</body>
</html>
"""

@router.get("/privacy", response_class=HTMLResponse)
async def get_privacy_policy():
    """Serves the responsive, compliant ZENOVA Privacy Policy HTML page."""
    return HTMLResponse(content=PRIVACY_HTML)

@router.get("/terms", response_class=HTMLResponse)
async def get_terms_of_service():
    """Serves the responsive, compliant ZENOVA Terms of Service & EULA HTML page."""
    return HTMLResponse(content=TERMS_HTML)

@router.get("/delete-account", response_class=HTMLResponse)
async def get_delete_account_portal():
    """Serves the public account deletion information and request portal."""
    return HTMLResponse(content=DELETE_ACCOUNT_HTML)
