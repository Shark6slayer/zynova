import React from 'react';
import { FileQuestion, Home, Shield } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const NotFoundView: React.FC = () => {
  const attemptedPath =
    typeof window !== 'undefined' ? window.location.pathname : '';

  return (
    <LegalPageLayout
      title="404 — Page Not Found"
      description="The requested ZENOVA page could not be found."
      canonicalPath="/"
      subtitle="The URL you requested does not exist on ZENOVA."
      icon={<FileQuestion className="w-6 h-6" />}
      iconBgClass="bg-amber-500/10 border-amber-500/20 text-amber-400"
    >
      <section className="p-6 rounded-3xl bg-slate-900/80 border border-white/10 space-y-4">
        <p className="text-sm text-slate-300 leading-relaxed">
          We couldn&apos;t find a page matching{' '}
          <code className="px-2 py-0.5 rounded bg-black/50 text-purple-300 text-xs font-mono">
            {attemptedPath || '/'}
          </code>
          .
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <a
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white transition"
          >
            <Home className="w-4 h-4" />
            <span>Go to ZENOVA Home</span>
          </a>
          <a
            href="/privacy-policy"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-slate-200 transition"
          >
            <Shield className="w-4 h-4 text-purple-400" />
            <span>Privacy Policy</span>
          </a>
        </div>
      </section>
    </LegalPageLayout>
  );
};
