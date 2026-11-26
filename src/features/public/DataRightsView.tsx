import React from 'react';
import { Database, Lock, Download, Trash2 } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const DataRightsView: React.FC = () => {
  return (
    <LegalPageLayout
      title="Data Rights & Privacy Controls"
      description="Your data sovereignty rights on ZENOVA under the DPDP Act and international privacy standards, including access, correction, consent withdrawal, and erasure."
      canonicalPath="/data-rights"
      subtitle="Effective Date: November 26, 2026"
      icon={<Database className="w-6 h-6" />}
    >
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Sovereign Data Rights</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          In accordance with India&apos;s Digital Personal Data Protection (DPDP) Act and international privacy principles, ZENOVA provides transparent control over your personal data.
        </p>
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-white/10 space-y-2">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Download className="w-4 h-4 text-purple-400" />
            <span>Right to Access &amp; Summary</span>
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            You can view your account profile, connected integrations, and activity records directly in Settings or request a data summary from our Data Protection Officer.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-white/10 space-y-2">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Lock className="w-4 h-4 text-emerald-400" />
            <span>Right to Correction &amp; Withdrawal</span>
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Update inaccurate profile details anytime in Settings, or revoke third-party OAuth integrations (such as Instagram/Meta) with immediate token invalidation.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-white/10 space-y-2 sm:col-span-2">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Trash2 className="w-4 h-4 text-rose-400" />
            <span>Right to Erasure (Account &amp; Data Deletion)</span>
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            You may permanently delete your account and associated personal data at any time. Visit our{' '}
            <a href="/delete-account" className="text-purple-400 underline hover:text-purple-300">
              Account &amp; Data Deletion page
            </a>{' '}
            for self-service instructions and deletion status verification.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">2. Grievance Redressal</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          To exercise any data subject right or escalate a privacy concern, contact our Grievance Officer at{' '}
          <a href="mailto:privacy@intellidev.in" className="text-purple-400 underline">
            privacy@intellidev.in
          </a>
          .
        </p>
      </section>
    </LegalPageLayout>
  );
};
