import React from 'react';
import { Shield, Lock } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const PrivacyPolicyView: React.FC = () => {
  return (
    <LegalPageLayout
      title="Privacy Policy"
      description="ZENOVA Privacy Policy covering DPDP Act compliance, Meta and Instagram Graph API disclosures, data storage, and user privacy rights."
      canonicalPath="/privacy-policy"
      subtitle="Last Updated: November 26, 2026"
      icon={<Shield className="w-6 h-6" />}
    >
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <span>1. Introduction &amp; Sovereign Data Commitment</span>
        </h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA (“we”, “our”, or “us”) is dedicated to protecting user privacy under the Digital Personal Data Protection (DPDP) Act of India and international data privacy principles. This policy governs how we collect, use, and protect your information across our web platform and digital ecosystem.
        </p>
      </section>

      {/* Meta & Instagram Specific Disclosures */}
      <section className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-purple-500/30">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Lock className="w-5 h-5 text-purple-400" />
          <span>2. Meta Platforms &amp; Instagram Graph API Data Disclosure</span>
        </h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          When you link your Instagram Business or Creator account to ZENOVA via Facebook Login, we request authorization to access the following scopes:
        </p>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li><strong>instagram_basic:</strong> To read your Instagram business profile identifier, username, account type, and public media counts.</li>
          <li><strong>instagram_manage_insights:</strong> To view high-level analytics for your imported media if requested.</li>
          <li><strong>pages_show_list &amp; pages_read_engagement:</strong> To verify your Facebook Pages linked to your Instagram professional account and issue delegated page access tokens.</li>
        </ul>

        <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-2">
          <h3 className="text-xs font-bold text-purple-300 uppercase tracking-wider">How Instagram Data is Handled &amp; Stored</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            - <strong>Token Security:</strong> All access tokens received from Meta are encrypted using envelope AES-256-GCM encryption with cryptographic keys managed by our sovereign Key Management Subsystem (KMS). Plaintext tokens are never logged or exposed in client bundles.<br />
            - <strong>Media Storage:</strong> When you choose to import media, files are fetched directly via encrypted HTTPS connections and saved to our private, secure Cloudflare R2 object storage with strict access controls. No intermediate copies reside on permanent local disks.<br />
            - <strong>Third-Party Sharing:</strong> We do NOT sell, rent, or transfer your Instagram data or media to third parties or advertising networks.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">3. Information We Collect</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          - <strong>Account Information:</strong> Name, username, email address, phone verification state, password hash (Argon2), and optional profile avatars.<br />
          - <strong>Usage &amp; Activity Data:</strong> Posts, stories, social notes, comments, and interactions within the platform.<br />
          - <strong>Device &amp; Security Signals:</strong> IP address, device session fingerprints, and public keys for verified biometric devices.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">4. User Rights, Deauthorization &amp; Data Deletion</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          In compliance with Meta Platform Terms and global privacy regulations, you have full sovereignty over your data:
        </p>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li><strong>Disconnecting from ZENOVA:</strong> You can disconnect your Instagram account anytime via <em>Settings &gt; Connected Accounts &gt; Disconnect</em>.</li>
          <li><strong>Meta Deauthorization:</strong> Removing the app from your Facebook Settings immediately deauthorizes ZENOVA and invalidates your stored tokens via our real-time deauthorization webhook.</li>
          <li><strong>Data Rights:</strong> Review your full privacy rights on our <a href="/data-rights" className="text-purple-400 underline hover:text-purple-300">Data Rights page</a>.</li>
          <li><strong>Account &amp; Data Deletion:</strong> You may request complete erasure of your data at any time by visiting our <a href="/delete-account" className="text-purple-400 underline hover:text-purple-300">Account &amp; Data Deletion page</a> or emailing our Data Protection Officer at <a href="mailto:privacy@intellidev.in" className="text-purple-400 underline">privacy@intellidev.in</a>.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">5. Contact &amp; Grievance Officer</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          For privacy concerns, DPDP grievance redressal, or data subject inquiries, contact:<br />
          <strong>Grievance Officer:</strong> <a href="mailto:privacy@intellidev.in" className="text-purple-400 underline">privacy@intellidev.in</a><br />
          <strong>Entity:</strong> ZENOVA Platforms / Intellidev Sovereign Systems
        </p>
      </section>
    </LegalPageLayout>
  );
};
