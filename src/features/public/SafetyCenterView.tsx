import React from 'react';
import { ShieldCheck, ShieldAlert, Users, Scale, Lock, Mail } from 'lucide-react';
import { LegalPageLayout } from './LegalPageLayout';

const SAFETY_RESOURCES = [
  {
    title: 'Child Safety Standards',
    desc: 'Zero-tolerance policy against CSAE/CSAM, reporting channels, and NCMEC/law enforcement escalation.',
    href: '/child-safety',
    icon: ShieldAlert,
    accent: 'text-red-400 border-red-500/30',
  },
  {
    title: 'Community Guidelines',
    desc: 'Standards for respectful behavior, authenticity, intellectual property, and prohibited conduct.',
    href: '/community-guidelines',
    icon: Users,
    accent: 'text-purple-400 border-purple-500/30',
  },
  {
    title: 'Content Moderation',
    desc: 'How automated filters, user reports, human review, and appeals work across ZENOVA.',
    href: '/content-moderation',
    icon: Scale,
    accent: 'text-amber-400 border-amber-500/30',
  },
  {
    title: 'Privacy & Data Rights',
    desc: 'DPDP Act protections, Meta Graph API disclosures, and your right to access or erase data.',
    href: '/data-rights',
    icon: Lock,
    accent: 'text-emerald-400 border-emerald-500/30',
  },
];

export const SafetyCenterView: React.FC = () => {
  return (
    <LegalPageLayout
      title="ZENOVA Safety Center"
      description="Central hub for ZENOVA safety policies, child protection standards, reporting mechanisms, and moderation transparency."
      canonicalPath="/safety"
      subtitle="Trust, Safety & Platform Integrity"
      icon={<ShieldCheck className="w-6 h-6" />}
      iconBgClass="bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
    >
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Protecting Our Community</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          Safety is foundational to ZENOVA. Explore our published policies, reporting tools, and enforcement standards below.
        </p>
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {SAFETY_RESOURCES.map((item) => {
          const Icon = item.icon;
          return (
            <a
              key={item.href}
              href={item.href}
              className={`block p-5 rounded-2xl bg-slate-900/80 border ${item.accent} hover:bg-slate-900 transition space-y-2`}
            >
              <div className="flex items-center gap-2 font-bold text-sm text-white">
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.title}</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{item.desc}</p>
            </a>
          );
        })}
      </section>

      <section className="p-6 rounded-3xl bg-slate-900/80 border border-white/10 space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Mail className="w-5 h-5 text-purple-400" />
          <span>2. Report a Safety Issue</span>
        </h2>
        <p className="text-xs text-slate-300 leading-relaxed">
          To report urgent child safety concerns, email{' '}
          <a href="mailto:child-safety@intellidev.in" className="text-purple-400 underline">
            child-safety@intellidev.in
          </a>
          . For general abuse or moderation issues, email{' '}
          <a href="mailto:safety@intellidev.in" className="text-purple-400 underline">
            safety@intellidev.in
          </a>{' '}
          or visit our{' '}
          <a href="/contact" className="text-purple-400 underline">
            Contact &amp; Support
          </a>{' '}
          page.
        </p>
      </section>
    </LegalPageLayout>
  );
};
