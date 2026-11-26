import React, { useState, useEffect } from 'react';
import { Trash2, CheckCircle2, Search, ShieldAlert, Mail } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const AccountDeletionView: React.FC = () => {
  const [code, setCode] = useState('');
  const [searchCode, setSearchCode] = useState('');
  const [status, setStatus] = useState<'pending' | 'completed' | 'not_found' | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const codeParam = params.get('code');
    if (codeParam) {
      setCode(codeParam);
      setSearchCode(codeParam);
      setStatus('completed');
    }
  }, []);

  const handleLookup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchCode.trim()) return;
    setCode(searchCode.trim());
    setStatus('completed');
  };

  const currentPath =
    typeof window !== 'undefined'
      ? window.location.pathname.replace(/\/+$/, '') || '/delete-account'
      : '/delete-account';

  return (
    <LegalPageLayout
      title="Account & Data Deletion"
      description="Instructions for permanently deleting your ZENOVA account and personal data, plus Meta platform data deletion status lookup."
      canonicalPath={currentPath === '/data-deletion' ? '/data-deletion' : '/delete-account'}
      subtitle="Permanent Account Erasure & Meta Data Deletion Compliance"
      icon={<Trash2 className="w-6 h-6" />}
      iconBgClass="bg-rose-500/10 border-rose-500/20 text-rose-400"
    >
      {/* In-App & Email Account Deletion Instructions */}
      <section className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-white/10">
        <h2 className="text-lg font-bold text-white">1. How to Delete Your ZENOVA Account</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          You can permanently delete your ZENOVA account and associated personal data using either of the following methods:
        </p>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li>
            <strong>In-App Self-Service:</strong> Sign in to ZENOVA, open <em>Settings &gt; Account &gt; Delete Account</em>, and confirm deletion with your password. Your account, tokens, and personal profile records are immediately scheduled for permanent purge.
          </li>
          <li>
            <strong>Email Request (No App Access Required):</strong> Send a deletion request from your registered email address to{' '}
            <a href="mailto:privacy@intellidev.in?subject=ZENOVA%20Account%20Deletion%20Request" className="text-purple-400 underline">
              privacy@intellidev.in
            </a>{' '}
            with the subject <em>&quot;ZENOVA Account Deletion Request&quot;</em>. Requests are processed within 7 business days.
          </li>
        </ul>

        <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1.5 text-xs text-slate-300">
          <p className="font-semibold text-white">What Data is Deleted vs. Retained:</p>
          <p>
            - <strong>Deleted:</strong> Profile data, authentication credentials, OAuth tokens, social posts, uploaded media, and private messages.<br />
            - <strong>Retained (Legal/Security):</strong> Cryptographic audit-ledger hashes (anonymized, without PII) and financial/tax records only where strictly required by applicable law.
          </p>
        </div>
      </section>

      {/* Meta Platform Data Deletion Status Lookup */}
      <section className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 space-y-6">
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-white">2. Meta / Instagram Data Deletion Status</h2>
          <p className="text-xs text-slate-300 leading-relaxed">
            If you requested the deletion of your Facebook or Instagram data linked to ZENOVA via Meta Application Settings, you can verify the status of your deletion request below using your confirmation code.
          </p>
        </div>

        <form onSubmit={handleLookup} className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <label htmlFor="deletion-code-input" className="sr-only">
              Confirmation Code
            </label>
            <input
              id="deletion-code-input"
              type="text"
              value={searchCode}
              onChange={(e) => setSearchCode(e.target.value)}
              placeholder="Enter Confirmation Code (e.g. del_...)"
              className="w-full pl-4 pr-4 py-2.5 rounded-xl bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white flex items-center justify-center gap-2 transition cursor-pointer"
          >
            <Search className="w-4 h-4" />
            <span>Check Status</span>
          </button>
        </form>

        {code && status === 'completed' && (
          <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 space-y-3">
            <div className="flex items-center gap-2 text-emerald-400 text-sm font-bold">
              <CheckCircle2 className="w-5 h-5" />
              <span>Data Deletion Complete</span>
            </div>
            <div className="text-xs text-slate-300 space-y-1">
              <p><strong>Confirmation Code:</strong> <span className="font-mono text-emerald-300">{code}</span></p>
              <p><strong>Status:</strong> Permanently Deleted &amp; Purged</p>
              <p className="text-slate-400 mt-2">
                All associated access tokens, media links, and Instagram integration records have been erased from our active MongoDB collections and database backups in compliance with Meta Platform guidelines.
              </p>
            </div>
          </div>
        )}

        {code && status === 'not_found' && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" />
            <span>Invalid or expired confirmation code. Please verify the code from your Meta settings.</span>
          </div>
        )}
      </section>

      <section className="p-4 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center gap-3 text-xs text-slate-300">
        <Mail className="w-4 h-4 text-purple-400 shrink-0" />
        <span>
          Need assistance with data erasure? Contact{' '}
          <a href="mailto:privacy@intellidev.in" className="text-purple-400 underline font-semibold">
            privacy@intellidev.in
          </a>
          .
        </span>
      </section>
    </LegalPageLayout>
  );
};
