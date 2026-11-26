import React from 'react';
import { FileText } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const TermsOfServiceView: React.FC = () => {
  return (
    <LegalPageLayout
      title="Terms of Service"
      description="ZENOVA Terms of Service governing platform access, acceptable use, Meta integrations, and account termination."
      canonicalPath="/terms"
      subtitle="Effective Date: November 26, 2026"
      icon={<FileText className="w-6 h-6" />}
    >
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Acceptance of Terms</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          By accessing or using ZENOVA and any associated services, you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use our services.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">2. Meta &amp; Third-Party Integrations</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA offers integrations with external third-party platforms, including Meta Platforms, Inc. (Instagram Graph API). By connecting your Instagram account, you acknowledge and agree that:
        </p>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li>You are the legitimate administrator or authorized user of the connected Instagram professional/creator account and linked Facebook Page.</li>
          <li>Your use of Meta services is governed by the Meta Terms of Service and Platform Terms.</li>
          <li>You will not use Instagram synchronization to import, distribute, or publish unlawful, defamatory, or copyright-infringing content.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">3. User Conduct &amp; Acceptable Use</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Users agree to comply with our <a href="/community-guidelines" className="text-purple-400 underline hover:text-purple-300">Community Guidelines</a> and <a href="/child-safety" className="text-purple-400 underline hover:text-purple-300">Child Safety Standards</a>, and not to engage in malicious activities, spamming, automated scraping, reverse engineering, or exploiting vulnerabilities on the ZENOVA platform.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">4. Limitation of Liability &amp; Termination</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA provides its services on an &quot;as is&quot; and &quot;as available&quot; basis. We reserve the right to suspend or terminate accounts that violate our community standards, safety protocols, or third-party partner agreements.
        </p>
      </section>
    </LegalPageLayout>
  );
};
