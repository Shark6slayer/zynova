import React from 'react';
import { Users, ShieldCheck, AlertCircle } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const CommunityGuidelinesView: React.FC = () => {
  return (
    <LegalPageLayout
      title="Community Guidelines"
      description="ZENOVA Community Guidelines for safe, respectful, and lawful interactions across social feeds, Connect messaging, video, and AI tools."
      canonicalPath="/community-guidelines"
      subtitle="Effective Date: November 26, 2026"
      icon={<Users className="w-6 h-6" />}
    >
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Our Community Purpose</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA brings together communication, social sharing, commerce, video, and AI productivity. These Community Guidelines apply to all users, creators, and merchants across every feature of the platform.
        </p>
      </section>

      <section className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-purple-500/30">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-purple-400" />
          <span>2. Expected Conduct</span>
        </h2>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li><strong>Respect Others:</strong> Engage constructively without harassment, bullying, hate speech, or targeted intimidation.</li>
          <li><strong>Authenticity:</strong> Do not impersonate individuals, brands, or ZENOVA staff, or operate deceptive spam networks.</li>
          <li><strong>Privacy:</strong> Do not publish private personal information (doxxing), non-consensual intimate media, or confidential credentials.</li>
          <li><strong>Intellectual Property:</strong> Only upload or share media, audio, and text you own or have permission to distribute.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-rose-400" />
          <span>3. Zero-Tolerance Violations</span>
        </h2>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li>Child Sexual Abuse Material (CSAM) or exploitation of minors (see <a href="/child-safety" className="text-purple-400 underline">Child Safety Standards</a>).</li>
          <li>Credible threats of violence, terrorism, or self-harm encouragement.</li>
          <li>Fraud, financial scams, phishing, or distribution of malware.</li>
          <li>Automated scraping, circumvention of security controls, or abuse of AI generation tools.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">4. Enforcement</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Violations may result in content removal, feature restrictions, temporary suspension, or permanent account termination. Learn more in our <a href="/content-moderation" className="text-purple-400 underline">Content Moderation Policy</a>.
        </p>
      </section>
    </LegalPageLayout>
  );
};
