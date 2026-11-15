import React from 'react';
import { FileText, ArrowLeft, ShieldCheck } from 'lucide-react';

export const TermsOfServiceView: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-white p-6 md:p-12 max-w-4xl mx-auto space-y-8 font-sans">
      <div className="flex items-center justify-between border-b border-white/10 pb-6">
        <div>
          <a
            href="/"
            className="inline-flex items-center gap-2 text-xs text-purple-400 hover:text-purple-300 font-semibold mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Zynova</span>
          </a>
          <h1 className="text-3xl font-extrabold tracking-tight">Terms of Service</h1>
          <p className="text-xs text-slate-400 mt-1">Effective Date: November 15, 2026</p>
        </div>
        <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-2xl text-purple-400">
          <FileText className="w-6 h-6" />
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Acceptance of Terms</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          By accessing or using Zynova and any associated services, you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use our services.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">2. Meta & Third-Party Integrations</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Zynova offers integrations with external third-party platforms, including Meta Platforms, Inc. (Instagram Graph API). By connecting your Instagram account, you acknowledge and agree that:
        </p>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li>You are the legitimate administrator or authorized user of the connected Instagram professional/creator account and linked Facebook Page.</li>
          <li>Your use of Meta services is governed by the Meta Terms of Service and Platform Terms.</li>
          <li>You will not use Instagram synchronization to import, distribute, or publish unlawful, defamatory, or copyright-infringing content.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">3. User Conduct & Acceptable Use</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Users agree not to engage in malicious activities, spamming, automated scraping, reverse engineering, or exploiting vulnerabilities on the Zynova platform.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">4. Limitation of Liability & Termination</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Zynova provides its services on an "as is" and "as available" basis. We reserve the right to suspend or terminate accounts that violate our community standards, security protocols, or third-party partner agreements.
        </p>
      </section>
    </div>
  );
};
