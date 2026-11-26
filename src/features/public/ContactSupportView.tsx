import React from 'react';
import { Mail, ShieldAlert, MessageSquare, Globe } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const ContactSupportView: React.FC = () => {
  return (
    <LegalPageLayout
      title="Contact & Support"
      description="Official ZENOVA support, privacy, child safety, and legal contact channels at Intellidev Sovereign Systems."
      canonicalPath="/contact"
      subtitle="ZENOVA Platforms / Intellidev Sovereign Systems"
      icon={<Mail className="w-6 h-6" />}
    >
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Official Contact Channels</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Reach the appropriate ZENOVA team directly using the verified email addresses below.
        </p>
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-white/10 space-y-2">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-purple-400" />
            <span>General Support &amp; Account Help</span>
          </h3>
          <p className="text-xs text-slate-400">
            Account access, bug reports, billing, and general inquiries.
          </p>
          <p className="text-xs font-mono">
            <a href="mailto:support@intellidev.in" className="text-purple-400 underline">
              support@intellidev.in
            </a>
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-white/10 space-y-2">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Mail className="w-4 h-4 text-emerald-400" />
            <span>Privacy &amp; Data Protection Officer</span>
          </h3>
          <p className="text-xs text-slate-400">
            DPDP Act grievance redressal, data access, and deletion requests.
          </p>
          <p className="text-xs font-mono">
            <a href="mailto:privacy@intellidev.in" className="text-purple-400 underline">
              privacy@intellidev.in
            </a>
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-red-500/30 space-y-2">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-400" />
            <span>Child Safety Point of Contact</span>
          </h3>
          <p className="text-xs text-slate-400">
            Urgent CSAE/CSAM reports and Google Play child safety communications.
          </p>
          <p className="text-xs font-mono">
            <a href="mailto:child-safety@intellidev.in" className="text-purple-400 underline">
              child-safety@intellidev.in
            </a>
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-white/10 space-y-2">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Globe className="w-4 h-4 text-sky-400" />
            <span>Trust, Safety &amp; Moderation</span>
          </h3>
          <p className="text-xs text-slate-400">
            Abuse reports, content moderation appeals, and legal notices.
          </p>
          <p className="text-xs font-mono">
            <a href="mailto:safety@intellidev.in" className="text-purple-400 underline">
              safety@intellidev.in
            </a>
          </p>
        </div>
      </section>
    </LegalPageLayout>
  );
};
