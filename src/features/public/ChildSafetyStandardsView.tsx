import React from 'react';
import { ShieldAlert, Mail, AlertTriangle, FileCheck, CheckCircle2 } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

export const ChildSafetyStandardsView: React.FC = () => {
  return (
    <LegalPageLayout
      title="Child Safety Standards"
      description="ZENOVA Child Safety Standards and zero-tolerance policy against Child Sexual Abuse and Exploitation (CSAE) and CSAM."
      canonicalPath="/child-safety"
      subtitle="Effective Date: November 26, 2026 • Website: https://www.intellidev.in"
      icon={<ShieldAlert className="w-6 h-6" />}
      iconBgClass="bg-red-500/10 border-red-500/20 text-red-400"
    >
      {/* 1. Our Commitment */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Our Commitment</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA is committed to protecting children and preventing Child Sexual Abuse and Exploitation (CSAE) across its services.
        </p>
        <p className="text-sm text-slate-300 leading-relaxed">
          We maintain a zero-tolerance policy toward child sexual abuse material (CSAM), child exploitation, grooming, sexual solicitation of minors, and any content or behavior that endangers children.
        </p>
      </section>

      {/* 2. Strictly Prohibited Activities */}
      <section className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-red-500/30">
        <h2 className="text-lg font-bold text-red-400 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <span>2. Strictly Prohibited Activities</span>
        </h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          The following activities are strictly prohibited on ZENOVA:
        </p>
        <ul className="space-y-2 text-xs text-slate-300 pl-4 list-disc">
          <li>Creating, uploading, sharing, or distributing CSAM.</li>
          <li>Sexual exploitation or abuse of minors.</li>
          <li>Grooming or attempting to groom children.</li>
          <li>Sexual solicitation of minors.</li>
          <li>Sexualized depictions of children.</li>
          <li>Offering, requesting, or exchanging sexual images involving minors.</li>
          <li>Trafficking, coercion, or exploitation of children.</li>
          <li>Encouraging or facilitating child abuse.</li>
          <li>Attempting to contact children for sexual purposes.</li>
          <li>Circumventing safety systems to exploit minors.</li>
        </ul>
        <div className="p-4 rounded-2xl bg-black/40 border border-white/5">
          <p className="text-xs text-slate-300 leading-relaxed">
            These restrictions apply to profiles, posts, comments, messages, videos, images, AI-generated content, and all other platform features.
          </p>
        </div>
      </section>

      {/* 3. Reporting Child Safety Concerns */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <FileCheck className="w-5 h-5 text-purple-400" />
          <span>3. Reporting Child Safety Concerns</span>
        </h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Users can report suspected child exploitation or unsafe content through available in-app reporting functionality.
        </p>
        <p className="text-xs text-slate-300 font-semibold">Reports should include:</p>
        <ul className="space-y-1 text-xs text-slate-300 pl-4 list-disc">
          <li>The relevant account or content identifier.</li>
          <li>A clear description of the safety concern.</li>
          <li>Supporting information, where appropriate.</li>
        </ul>
        <div className="p-4 rounded-2xl bg-purple-500/10 border border-purple-500/20 space-y-2">
          <p className="text-xs text-slate-300 leading-relaxed">
            Users may also contact our designated safety team directly:
          </p>
          <p className="text-sm text-purple-300 font-mono flex items-center gap-2">
            <Mail className="w-4 h-4 text-purple-400" />
            <span>
              Child Safety Email:{' '}
              <a href="mailto:child-safety@intellidev.in" className="font-bold underline">
                child-safety@intellidev.in
              </a>
            </span>
          </p>
          <p className="text-xs text-slate-400">
            Reports involving suspected child exploitation will be prioritized for immediate review.
          </p>
        </div>
        <p className="text-xs text-red-400 font-medium">
          Do not download, copy, screenshot, or redistribute suspected CSAM when reporting it.
        </p>
      </section>

      {/* 4. Investigation and Enforcement */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <span>4. Investigation and Enforcement</span>
        </h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Where we obtain actual knowledge of suspected CSAM or child exploitation, we will take immediate and appropriate action in accordance with applicable law and our published procedures.
        </p>
        <p className="text-xs text-slate-300 font-semibold">Depending on the circumstances, actions may include:</p>
        <ul className="space-y-1 text-xs text-slate-300 pl-4 list-disc">
          <li>Removing or restricting access to violating content.</li>
          <li>Suspending or terminating offending accounts.</li>
          <li>Restricting upload, streaming, or messaging privileges.</li>
          <li>Preserving relevant information where legally permitted or required.</li>
          <li>Escalating confirmed cases to appropriate authorities.</li>
          <li>Cooperating fully with lawful investigations.</li>
        </ul>
      </section>

      {/* 5. Reporting to Authorities */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">5. Reporting to Authorities</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA maintains a formal process for reporting confirmed CSAM to the appropriate authority, including the National Center for Missing &amp; Exploited Children (NCMEC) or the relevant regional authority, as applicable to the incident and legal obligations.
        </p>
        <p className="text-sm text-slate-300 leading-relaxed">
          In India, reports will be escalated to the appropriate law enforcement authorities, Cyber Crime units, and relevant government reporting channels.
        </p>
      </section>

      {/* 6. Child Safety Contact */}
      <section className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-purple-500/30">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Mail className="w-5 h-5 text-purple-400" />
          <span>6. Child Safety Point of Contact</span>
        </h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          ZENOVA designates a responsible Child Safety Point of Contact to receive communications from Google Play and other relevant parties concerning child sexual abuse and exploitation.
        </p>
        <div className="p-4 rounded-2xl bg-black/40 border border-white/10 space-y-2">
          <p className="text-xs text-slate-300">
            <strong>Designated Contact:</strong> ZENOVA Child Safety &amp; Trust Team
          </p>
          <p className="text-xs text-slate-300">
            <strong>Email:</strong>{' '}
            <a href="mailto:child-safety@intellidev.in" className="text-purple-400 underline">
              child-safety@intellidev.in
            </a>
          </p>
          <p className="text-xs text-slate-400 mt-2">
            The designated representative is responsible for coordinating policy enforcement, reviewing incoming reports, liaising with regulatory bodies, and facilitating prompt safety actions.
          </p>
        </div>
      </section>

      {/* 7. User Cooperation */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">7. User Cooperation</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Users are expected to report suspected child exploitation and cooperate with legitimate safety investigations.
        </p>
        <p className="text-sm text-slate-300 leading-relaxed">
          False, malicious, or abusive reporting may also result in account restrictions or termination.
        </p>
      </section>

      {/* 8. Policy Updates */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">8. Policy Updates</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          These standards may be updated as ZENOVA&apos;s services, safety systems, and applicable legal requirements evolve.
        </p>
      </section>
    </LegalPageLayout>
  );
};
