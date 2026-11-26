import React from 'react';
import { Scale, Eye, Flag, CheckCircle2 } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const ContentModerationView: React.FC = () => {
  return (
    <LegalPageLayout
      title="Content Moderation"
      description="How ZENOVA detects, reviews, enforces, and handles appeals for policy violations and user safety reports."
      canonicalPath="/content-moderation"
      subtitle="Effective Date: November 26, 2026"
      icon={<Scale className="w-6 h-6" />}
    >
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Moderation Philosophy</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA combines automated safety filters, user reporting workflows, and human trust-and-safety review to keep the platform safe while respecting lawful expression.
        </p>
      </section>

      <section className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-white/10">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Eye className="w-5 h-5 text-purple-400" />
          <span>2. Detection &amp; Review Process</span>
        </h2>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li><strong>Automated Safeguards:</strong> Proactive screening for spam, malicious links, abusive media, and AI prompt safety boundaries.</li>
          <li><strong>User Reports:</strong> In-app reporting on posts, comments, profiles, videos, and messages routes directly to our moderation queue.</li>
          <li><strong>Priority Escalation:</strong> Reports involving child safety, imminent harm, or illegal activity are prioritized for immediate review.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Flag className="w-5 h-5 text-amber-400" />
          <span>3. Enforcement Actions</span>
        </h2>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li>Content removal or visibility restriction.</li>
          <li>Temporary suspension of posting, streaming, or messaging privileges.</li>
          <li>Permanent account termination for severe or repeated violations.</li>
          <li>Reporting to relevant legal authorities where required by law.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <span>4. Appeals &amp; Contact</span>
        </h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          If you believe a moderation action was taken in error, you may contact our Trust &amp; Safety team via <a href="/contact" className="text-purple-400 underline">Contact Support</a> or email <a href="mailto:safety@intellidev.in" className="text-purple-400 underline">safety@intellidev.in</a> with your account identifier and context.
        </p>
      </section>
    </LegalPageLayout>
  );
};
