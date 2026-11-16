import React, { useEffect } from 'react';
import { Shield, Lock, Eye, Server, Check, ArrowRight, UserCheck, Key, RefreshCw, FileText } from 'lucide-react';
import { LegalLayout } from '../../components/layout/LegalLayout';

export const PrivacyPolicyView: React.FC = () => {
  useEffect(() => {
    document.title = 'Zenova Privacy Policy';
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) {
      metaDesc.setAttribute('content', 'Zenova Privacy Policy. Discover how we protect your sovereign data, manage credentials, and handle Meta & Instagram integrations.');
    }
  }, []);

  const sections = [
    { id: 'intro', title: 'Introduction and Scope' },
    { id: 'information-collected', title: 'Information We Collect' },
    { id: 'personal-info', title: 'Personal Information' },
    { id: 'account-auth', title: 'Account Registration & Authentication' },
    { id: 'facebook-login', title: 'Facebook Login Integration' },
    { id: 'instagram-integration', title: 'Instagram Integration & Permissions' },
    { id: 'user-content', title: 'User-Generated Content' },
    { id: 'device-tech', title: 'Device and Technical Information' },
    { id: 'cookies', title: 'Cookies & Similar Technologies' },
    { id: 'how-we-use', title: 'How We Use Collected Information' },
    { id: 'storage-security', title: 'Data Storage and Security' },
    { id: 'third-parties', title: 'Third-Party Services & Integrations' },
    { id: 'data-sharing', title: 'Data Sharing and Disclosure' },
    { id: 'user-rights', title: 'User Rights & Privacy Choices' },
    { id: 'data-deletion', title: 'Account & Data Deletion Requests' },
    { id: 'children', title: "Children's Privacy" },
    { id: 'transfers', title: 'International Data Transfers' },
    { id: 'updates', title: 'Policy Updates' },
    { id: 'contact', title: 'Contact Information' },
  ];

  return (
    <LegalLayout
      title="Zenova Privacy Policy"
      subtitle="Our commitment to safeguarding your sovereign data, managing privacy, and securing external integrations across the Zenova ecosystem."
      lastUpdated="November 16, 2026"
      badgeText="DPDP & Global Privacy Compliance"
      icon={<Shield className="w-16 h-16 text-purple-400" />}
      sections={sections}
    >
      {/* 1. Introduction and Scope */}
      <section id="intro" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">1.</span> Introduction and Scope
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova (“we”, “our”, or “us”) provides an integrated super application spanning social networking, real-time communication, intelligent assistant workflows, and creator tools. We believe that privacy is a fundamental human right.
        </p>
        <p className="text-sm leading-relaxed text-slate-300">
          This Privacy Policy applies to all users accessing or interacting with Zenova via our web portal (<a href="https://www.intellidev.in" className="text-purple-400 hover:underline">https://www.intellidev.in</a>), official subdomains, APIs, and mobile applications. It governs the manner in which we collect, store, process, protect, and delete data under the Digital Personal Data Protection (DPDP) Act of India, Meta Platform Policies, and applicable international privacy frameworks.
        </p>
      </section>

      {/* 2. Information We Collect */}
      <section id="information-collected" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">2.</span> Information We Collect
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          We collect only information necessary to deliver seamless, authenticated, and secure services. Information is collected directly when you provide it, automatically when you navigate the platform, or via external accounts when explicitly authorized by you.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="p-4 rounded-2xl bg-white/5 border border-white/10 space-y-2">
            <h3 className="text-xs font-bold text-purple-300 uppercase tracking-wider">Directly Provided</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Profile details, email address, password credentials, uploaded images, audio messages, videos, posts, stories, and customer support queries.
            </p>
          </div>
          <div className="p-4 rounded-2xl bg-white/5 border border-white/10 space-y-2">
            <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider">Third-Party Authorized</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Public Instagram profile metadata, creator media IDs, post captions, thumbnails, and Facebook Page identifiers when connected via Meta OAuth.
            </p>
          </div>
        </div>
      </section>

      {/* 3. Personal Information */}
      <section id="personal-info" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">3.</span> Personal Information
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Personal data includes identifiers that allow you to be recognized or contacted:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li><strong>Identity Data:</strong> Full name, chosen username, handle, profile avatar, and biographical bio.</li>
          <li><strong>Contact Data:</strong> Primary email address and phone number (if linked for verified two-factor authentication or delivery alerts).</li>
          <li><strong>Cryptographic Identity:</strong> Public device keys and biometric challenge verifications stored for passkey authentication.</li>
        </ul>
      </section>

      {/* 4. Account Registration & Authentication */}
      <section id="account-auth" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">4.</span> Account Registration & Authentication
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          When creating a Zenova sovereign account, passwords are never stored in clear text. All passwords are cryptographic hashes using industry-standard, memory-hard algorithms (Argon2id/Bcrypt). Sessions are maintained via cryptographically signed JSON Web Tokens (JWT) using HS256 with short expiration intervals and sliding refresh tokens.
        </p>
        <p className="text-sm leading-relaxed text-slate-300">
          Tokens revoked upon logout are indexed in an automated TTL revocation registry in our database to prevent token replay attacks.
        </p>
      </section>

      {/* 5. Facebook Login Integration */}
      <section id="facebook-login" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">5.</span> Facebook Login Integration
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova provides authentication and authorization linking via <strong>Facebook Login</strong> and <strong>Facebook Login for Business</strong> (Meta Graph API v21.0). When initiating Facebook Login:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li>We request authorization through official dialogs (<code className="text-purple-300">https://www.facebook.com/dialog/oauth</code>).</li>
          <li>We generate a single-use 32-byte cryptographic random state stored temporarily in a memory cache (TTL 600 seconds) to prevent Cross-Site Request Forgery (CSRF). State tokens do not expose your user ID.</li>
          <li>We exchange the returned authorization code for access tokens strictly over encrypted server-to-server POST channels with payload form data, ensuring secrets never leak in URL parameters.</li>
          <li>We only access permissions explicitly authorized by you during the dialog.</li>
        </ul>
      </section>

      {/* 6. Instagram Integration & Permissions */}
      <section id="instagram-integration" className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-purple-500/30">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Lock className="w-5 h-5 text-purple-400" />
          <span><span className="text-purple-400">6.</span> Instagram Integration & Permissions</span>
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova allows creators and business accounts to sync and showcase their professional media inside their Zenova feed and profile.
        </p>
        
        <h3 className="text-xs font-bold text-purple-300 uppercase tracking-wider pt-2">Authorized Meta Scopes & Purpose</h3>
        <div className="space-y-3">
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5">
            <span className="font-mono text-xs text-purple-300 font-bold">instagram_basic</span>
            <p className="text-xs text-slate-300 mt-1">
              Enables Zenova to read your Instagram professional account ID, username, profile picture URL, media count, and public post references.
            </p>
          </div>
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5">
            <span className="font-mono text-xs text-purple-300 font-bold">instagram_manage_insights</span>
            <p className="text-xs text-slate-300 mt-1">
              Enables you to view high-level aggregate engagement metrics (views, likes, comments) for media items you explicitly choose to import.
            </p>
          </div>
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5">
            <span className="font-mono text-xs text-purple-300 font-bold">pages_show_list & pages_read_engagement</span>
            <p className="text-xs text-slate-300 mt-1">
              Required by Meta architecture to detect Facebook Pages linked to your Instagram professional asset and generate authorized delegated page tokens.
            </p>
          </div>
        </div>

        <h3 className="text-xs font-bold text-purple-300 uppercase tracking-wider pt-4">Token Encryption & Protection</h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          Access tokens granted by Meta are immediately protected using envelope encryption (NIST SP 800-38D AES-256-GCM with HKDF-SHA256 key derivation) via our Key Management Subsystem (KMS). Tokens are never logged, never exposed to browser client code, and never transferred outside our secure backend runtime.
        </p>

        <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider pt-2">Our Strict Boundaries: What Zenova Never Does</h3>
        <ul className="list-disc pl-5 space-y-1.5 text-xs text-slate-300">
          <li>We <strong>NEVER</strong> post, comment, like, or publish content on your Instagram or Facebook account.</li>
          <li>We <strong>NEVER</strong> access your private Direct Messages (DMs) or message history.</li>
          <li>We <strong>NEVER</strong> modify your Instagram account settings or follower graph.</li>
          <li>We <strong>NEVER</strong> sell or distribute Instagram data to third-party ad brokers.</li>
        </ul>
      </section>

      {/* 7. User-Generated Content */}
      <section id="user-content" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">7.</span> User-Generated Content
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          You retain full ownership of all posts, images, videos, notes, captions, and comments you publish on Zenova. When you publish content publicly within the discovery feed, you grant Zenova a non-exclusive license solely to host, render, and display your content to other users across our application interface.
        </p>
      </section>

      {/* 8. Device and Technical Information */}
      <section id="device-tech" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">8.</span> Device and Technical Information
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          To maintain security, enforce API rate limits, and detect fraudulent behavior, our servers automatically log technical metadata:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li><strong>Network Identifiers:</strong> IP address and approximate geographical region (country/city level).</li>
          <li><strong>Client Signals:</strong> Operating system, browser type, device type (desktop, mobile), and user agent strings.</li>
          <li><strong>Security Telemetry:</strong> Anonymized request failure counts, preflight CORS origins, and rate-limiting buckets. Sensitive headers and query parameters are stripped by server logging filters.</li>
        </ul>
      </section>

      {/* 9. Cookies & Similar Technologies */}
      <section id="cookies" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">9.</span> Cookies & Similar Technologies
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova uses localized browser storage (HTML5 LocalStorage and secure session cookies) strictly for:
        </p>
        <ul className="list-disc pl-5 space-y-1.5 text-xs text-slate-300">
          <li>Persisting your active authentication access and refresh credentials.</li>
          <li>Saving your chosen visual theme, appearance mode (system/dark/light), and interface language.</li>
          <li>Caching drafted posts locally so your work is never lost if your network connection drops.</li>
        </ul>
        <p className="text-sm leading-relaxed text-slate-300">
          We do not use invasive third-party cross-site tracking cookies.
        </p>
      </section>

      {/* 10. How We Use Collected Information */}
      <section id="how-we-use" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">10.</span> How We Use Collected Information
        </h2>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li>To authenticate your identity and protect against unauthorized account takeovers.</li>
          <li>To allow you to sync, browse, and import your authorized Instagram media to your Zenova profile.</li>
          <li>To deliver real-time notifications, chat messages, and social updates.</li>
          <li>To audit ledger checkpoints and verify tamper-proof data integrity.</li>
          <li>To comply with regulatory obligations and enforce our Terms of Service.</li>
        </ul>
      </section>

      {/* 11. Data Storage and Security */}
      <section id="storage-security" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">11.</span> Data Storage and Security
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Security is built into Zenova at the architectural level:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li><strong>Encryption in Transit:</strong> All HTTP communications are enforced over TLS 1.3 encryption. HSTS headers enforce secure connections across all domains.</li>
          <li><strong>Encryption at Rest:</strong> Sensitive tokens and credentials are protected with AES-256-GCM encryption. User databases are secured with encrypted storage volumes.</li>
          <li><strong>Cloud Object Storage:</strong> Media imported from Instagram is hosted in private Cloudflare R2 / S3-compatible storage with strict pre-signed URL access controls and MIME-type integrity checks.</li>
        </ul>
      </section>

      {/* 12. Third-Party Services & Integrations */}
      <section id="third-parties" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">12.</span> Third-Party Services & Integrations
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova interacts with select third-party infrastructure partners solely to deliver core services:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li><strong>Meta Platforms, Inc.:</strong> For Facebook Login and Instagram Graph API media queries.</li>
          <li><strong>Cloudflare:</strong> For edge CDN distribution, DDoS mitigation, and encrypted object media storage.</li>
          <li><strong>Render & Vercel:</strong> For cloud compute hosting and edge routing.</li>
        </ul>
      </section>

      {/* 13. Data Sharing and Disclosure */}
      <section id="data-sharing" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">13.</span> Data Sharing and Disclosure
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          We do not sell, monetize, or trade your personal or integrated account information. Data is disclosed only in the following limited circumstances:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li><strong>With Your Consent:</strong> When you choose to make a post public or share your profile.</li>
          <li><strong>Legal Compliance:</strong> When compelled by valid subpoenas, court orders, or enforceable governmental requests under Indian law.</li>
          <li><strong>Safety & Protection:</strong> To protect the vital interests, rights, property, or safety of Zenova users or the public.</li>
        </ul>
      </section>

      {/* 14. User Rights & Privacy Choices */}
      <section id="user-rights" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">14.</span> User Rights & Privacy Choices
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Under the Digital Personal Data Protection Act and global standards, you have the right to:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li>Access and review summary records of your personal data.</li>
          <li>Correct inaccurate or incomplete profile information.</li>
          <li>Withdraw authorization for third-party integrations at any time without terminating your Zenova account.</li>
          <li>Request complete erasure of your account and associated assets.</li>
        </ul>
      </section>

      {/* 15. Account Deletion and Data Deletion Requests */}
      <section id="data-deletion" className="space-y-4 p-6 rounded-3xl bg-slate-900/60 border border-white/10">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <RefreshCw className="w-5 h-5 text-purple-400" />
          <span><span className="text-purple-400">15.</span> Account Deletion & Data Deletion Requests</span>
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          We provide straightforward, immediate data deletion mechanisms for all users and Meta-connected accounts:
        </p>
        <div className="space-y-3 pt-2">
          <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <h4 className="text-xs font-bold text-white">1. In-App Third-Party Disconnect</h4>
            <p className="text-xs text-slate-300">
              Navigate to <em>Settings &gt; Connected Accounts &gt; Disconnect</em>. This immediately deletes your encrypted Meta access tokens and unlinks your Instagram profile from Zenova.
            </p>
          </div>
          <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <h4 className="text-xs font-bold text-white">2. Meta Deauthorization Webhook</h4>
            <p className="text-xs text-slate-300">
              If you remove Zenova from your Facebook Application Settings, Meta notifies our deauthorization endpoint (<code className="text-purple-300">/api/v1/instagram/deauthorize</code>). Our server automatically marks your connection inactive and purges stored tokens.
            </p>
          </div>
          <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <h4 className="text-xs font-bold text-white">3. Meta Data Deletion Callback & Verification Page</h4>
            <p className="text-xs text-slate-300">
              When a data deletion request is submitted via Facebook, our system returns a dedicated confirmation code and tracking URL. You can check the real-time status of your deletion request anytime at:
              <br />
              <a href="/data-deletion" className="text-purple-400 underline font-semibold mt-1 inline-block">
                https://www.intellidev.in/data-deletion
              </a>
            </p>
          </div>
          <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <h4 className="text-xs font-bold text-white">4. Complete Account Erasure</h4>
            <p className="text-xs text-slate-300">
              To delete your complete Zenova sovereign account and all associated posts, messages, and uploaded files, contact our Data Protection Officer at <a href="mailto:privacy@intellidev.in" className="text-purple-400 hover:underline">privacy@intellidev.in</a>. All personal records are purged within 30 days.
            </p>
          </div>
        </div>
      </section>

      {/* 16. Children's Privacy */}
      <section id="children" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">16.</span> Children's Privacy
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova is not intended for individuals under 13 years of age (or the minimum legal age for data processing in your jurisdiction). We do not knowingly collect personal information from children. If we discover that a child under 13 has provided personal data, we will immediately delete such records.
        </p>
      </section>

      {/* 17. International Data Transfers */}
      <section id="transfers" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">17.</span> International Data Transfers
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova's primary infrastructure is hosted in secure, certified cloud data centers. In the course of delivering global CDN content delivery and communicating with third-party APIs (such as Meta Platforms in the United States), your data may be processed across international borders with standard contractual protections and encryption safeguards in place.
        </p>
      </section>

      {/* 18. Policy Updates */}
      <section id="updates" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-purple-400">18.</span> Policy Updates
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          We may update this Privacy Policy from time to time to reflect product enhancements, API modifications, or regulatory updates. When significant changes occur, we will update the "Last Updated" date at the top of this page and post a prominent notice within the Zenova application interface.
        </p>
      </section>

      {/* 19. Contact Information */}
      <section id="contact" className="space-y-4 p-6 rounded-3xl bg-purple-950/20 border border-purple-500/20">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <UserCheck className="w-5 h-5 text-purple-400" />
          <span><span className="text-purple-400">19.</span> Contact Information & Grievance Redressal</span>
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          For any questions, concerns, or requests regarding this Privacy Policy or our data handling practices, please contact our Data Protection and Grievance Officer:
        </p>
        <div className="p-4 rounded-2xl bg-black/40 border border-white/5 text-xs text-slate-300 space-y-1.5 font-mono">
          <div><strong>Entity:</strong> Zenova Platforms / Intellidev Sovereign Systems</div>
          <div><strong>Email:</strong> <a href="mailto:privacy@intellidev.in" className="text-purple-400 hover:underline">privacy@intellidev.in</a></div>
          <div><strong>Website:</strong> <a href="https://www.intellidev.in" className="text-purple-400 hover:underline">https://www.intellidev.in</a></div>
          <div><strong>Address:</strong> Bangalore, Karnataka, India</div>
        </div>
      </section>
    </LegalLayout>
  );
};