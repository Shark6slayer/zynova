import React, { useEffect } from 'react';
import { FileText, ShieldAlert, Scale, CheckCircle2, AlertTriangle, HelpCircle } from 'lucide-react';
import { LegalLayout } from '../../components/layout/LegalLayout';

export const TermsOfServiceView: React.FC = () => {
  useEffect(() => {
    document.title = 'Zenova Terms of Service';
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) {
      metaDesc.setAttribute('content', 'Zenova Terms of Service. Understand user obligations, content licensing, acceptable use, and third-party Meta integration rules.');
    }
  }, []);

  const sections = [
    { id: 'acceptance', title: 'Introduction & Acceptance of Terms' },
    { id: 'eligibility', title: 'Eligibility' },
    { id: 'registration', title: 'User Account Registration' },
    { id: 'security', title: 'Account Security' },
    { id: 'acceptable-use', title: 'Acceptable Use Policy' },
    { id: 'prohibited', title: 'Prohibited Activities' },
    { id: 'ugc', title: 'User-Generated Content Ownership' },
    { id: 'moderation', title: 'Content Moderation' },
    { id: 'social-integrations', title: 'Social Media & Meta Integrations' },
    { id: 'third-parties', title: 'Third-Party Services' },
    { id: 'intellectual-property', title: 'Intellectual Property' },
    { id: 'service-availability', title: 'Service Availability' },
    { id: 'suspension-termination', title: 'Account Suspension & Termination' },
    { id: 'disclaimer', title: 'Disclaimer of Warranties' },
    { id: 'liability', title: 'Limitation of Liability' },
    { id: 'changes', title: 'Changes to Terms' },
    { id: 'governing-law', title: 'Governing Law and Jurisdiction' },
    { id: 'contact', title: 'Contact Information' },
  ];

  return (
    <LegalLayout
      title="Zenova Terms of Service"
      subtitle="The contractual terms and acceptable use standards governing your use of the Zenova sovereign platform and external integrations."
      lastUpdated="November 16, 2026"
      badgeText="User Agreement & Platform Rules"
      icon={<FileText className="w-16 h-16 text-indigo-400" />}
      sections={sections}
    >
      {/* 1. Introduction and Acceptance of Terms */}
      <section id="acceptance" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">1.</span> Introduction & Acceptance of Terms
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Welcome to Zenova. These Terms of Service (“Terms”) constitute a legally binding agreement between you (“User”, “you”, or “your”) and Zenova Platforms / Intellidev Sovereign Systems (“Zenova”, “we”, “our”, or “us”).
        </p>
        <p className="text-sm leading-relaxed text-slate-300">
          By registering an account, accessing, browsing, or using Zenova via our web portal (<a href="https://www.intellidev.in" className="text-indigo-400 hover:underline">https://www.intellidev.in</a>) or associated applications, you agree to be bound by these Terms and our Privacy Policy. If you do not agree to all terms and conditions, you must not access or use the platform.
        </p>
      </section>

      {/* 2. Eligibility */}
      <section id="eligibility" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">2.</span> Eligibility
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          You must be at least 13 years old (or the legal age of digital consent in your jurisdiction, whichever is higher) to use Zenova. If you are entering into these Terms on behalf of a company, organization, or other legal entity, you represent and warrant that you have full legal authority to bind that entity to these Terms.
        </p>
      </section>

      {/* 3. User Account Registration */}
      <section id="registration" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">3.</span> User Account Registration
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          To access core features of Zenova, you must create a sovereign user account. You agree to provide true, accurate, current, and complete information during registration and keep your account details updated. You may not impersonate any person or brand, use a username that violates trademark rights, or create accounts using automated bots without authorization.
        </p>
      </section>

      {/* 4. Account Security */}
      <section id="security" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">4.</span> Account Security
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          You are responsible for maintaining the confidentiality of your login credentials and cryptographic keys. You agree to notify Zenova immediately at <a href="mailto:security@intellidev.in" className="text-indigo-400 hover:underline">security@intellidev.in</a> upon becoming aware of any unauthorized access or breach of security. Zenova cannot and will not be liable for any loss or damage arising from your failure to protect your authentication tokens or device credentials.
        </p>
      </section>

      {/* 5. Acceptable Use Policy */}
      <section id="acceptable-use" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">5.</span> Acceptable Use Policy
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova is designed as an open, sovereign community for communication, commerce, and creative collaboration. You agree to use the platform in compliance with all applicable local, national, and international laws, including intellectual property laws and regulations governing electronic communications and digital payments.
        </p>
      </section>

      {/* 6. Prohibited Activities */}
      <section id="prohibited" className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-rose-500/30">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-rose-400" />
          <span><span className="text-rose-400">6.</span> Prohibited Activities</span>
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          You agree that you will NOT engage in any of the following prohibited behaviors on Zenova:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 text-xs text-slate-300">
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <span className="font-bold text-rose-300">Harmful & Malicious Code</span>
            <p>Uploading files containing viruses, Trojans, ransomware, malware, or exploiting platform APIs.</p>
          </div>
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <span className="font-bold text-rose-300">Harassment & Abuse</span>
            <p>Publishing defamatory, violent, sexually explicit, abusive, or discriminatory content against any individual or group.</p>
          </div>
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <span className="font-bold text-rose-300">System Abuse & Scraping</span>
            <p>Automated scraping, excessive rate-limit bypasses, denial of service attacks, or probing backend vulnerabilities.</p>
          </div>
          <div className="p-3.5 rounded-2xl bg-black/40 border border-white/5 space-y-1">
            <span className="font-bold text-rose-300">Deceptive Impersonation</span>
            <p>Falsely representing an affiliation with Zenova, Meta Platforms, or another brand or public figure.</p>
          </div>
        </div>
      </section>

      {/* 7. User-Generated Content Ownership */}
      <section id="ugc" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">7.</span> User-Generated Content Ownership
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          You retain all copyright and proprietary rights in the content, images, audio, video, notes, and captions that you upload or create on Zenova.
        </p>
        <p className="text-sm leading-relaxed text-slate-300">
          By uploading or publishing content to public areas of Zenova (such as public feeds or community channels), you grant Zenova a worldwide, non-exclusive, royalty-free license to host, display, transcode, and distribute your content across our platform interface solely to provide and improve the service.
        </p>
      </section>

      {/* 8. Content Moderation */}
      <section id="moderation" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">8.</span> Content Moderation
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova maintains automated safeguards and human review mechanisms to enforce community safety. All file uploads are validated via binary magic-byte inspection, strict MIME verification, and malware screening filters before being served. We reserve the right to remove or restrict any content that violates these Terms or applicable laws.
        </p>
      </section>

      {/* 9. Social Media & Meta Integrations */}
      <section id="social-integrations" className="space-y-4 p-6 rounded-3xl bg-slate-900/80 border border-indigo-500/30">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Scale className="w-5 h-5 text-indigo-400" />
          <span><span className="text-indigo-400">9.</span> Social Media & Meta Integrations</span>
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova integrates with Meta Platforms, Inc. via the Meta Graph API and Facebook Login. When utilizing connected account features:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-xs text-slate-300">
          <li><strong>Authority:</strong> You represent and warrant that you own or have explicit administrative authority over the connected Instagram Creator/Business account and linked Facebook Page.</li>
          <li><strong>Compliance with Meta Terms:</strong> You agree to comply with all applicable Meta Platform Terms, Instagram Terms of Use, and Community Guidelines.</li>
          <li><strong>Permitted Uses:</strong> You will use Instagram synchronization solely to import and showcase content you are legally permitted to distribute.</li>
          <li><strong>Revocation:</strong> You can disconnect your Instagram connection anytime via <em>Settings &gt; Connected Accounts &gt; Disconnect</em>, which immediately invalidates and deletes your stored tokens.</li>
        </ul>
      </section>

      {/* 10. Third-Party Services */}
      <section id="third-parties" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">10.</span> Third-Party Services
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          The platform may link to or incorporate services provided by third parties (such as cloud storage providers, payment gateways, or map services). Your use of third-party services is subject to their respective terms and policies. Zenova is not responsible for the availability, conduct, or policies of third parties.
        </p>
      </section>

      {/* 11. Intellectual Property */}
      <section id="intellectual-property" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">11.</span> Intellectual Property
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          All rights, title, and interest in and to the Zenova platform, including our interface, software code, UI designs, logos, trademarks, and documentation are the exclusive property of Zenova Platforms and its licensors. You may not copy, reverse engineer, decompile, or create derivative works without prior written consent.
        </p>
      </section>

      {/* 12. Service Availability */}
      <section id="service-availability" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">12.</span> Service Availability
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          We strive to provide continuous service availability. However, services may be subject to scheduled maintenance, software updates, or emergency outages. We do not guarantee uninterrupted or error-free platform operation at all times.
        </p>
      </section>

      {/* 13. Account Suspension & Termination */}
      <section id="suspension-termination" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">13.</span> Account Suspension & Termination
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          Zenova reserves the right to suspend, disable, or permanently terminate your account if you materially breach these Terms, engage in fraudulent behavior, fail security verifications, or if required by law or judicial order. You may terminate your account at any time by contacting our support team.
        </p>
      </section>

      {/* 14. Disclaimer of Warranties */}
      <section id="disclaimer" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">14.</span> Disclaimer of Warranties
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          THE ZENOVA PLATFORM AND ALL ASSOCIATED SERVICES ARE PROVIDED ON AN “AS IS” AND “AS AVAILABLE” BASIS WITHOUT WARRANTIES OF ANY KIND, WHETHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
        </p>
      </section>

      {/* 15. Limitation of Liability */}
      <section id="liability" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">15.</span> Limitation of Liability
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL ZENOVA, ITS AFFILIATES, OFFICERS, EMPLOYEES, OR AGENTS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES (INCLUDING LOSS OF PROFITS, DATA, OR GOODWILL) ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF OR INABILITY TO USE THE PLATFORM.
        </p>
      </section>

      {/* 16. Changes to Terms */}
      <section id="changes" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">16.</span> Changes to Terms
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          We may modify these Terms periodically. Notice of material modifications will be given by updating the Effective Date on this page and providing notification through the web application. Your continued use of Zenova following such notice constitutes your acceptance of the revised Terms.
        </p>
      </section>

      {/* 17. Governing Law and Jurisdiction */}
      <section id="governing-law" className="space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-white/10 pb-3 flex items-center gap-2">
          <span className="text-indigo-400">17.</span> Governing Law and Jurisdiction
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          These Terms and any dispute arising out of or related to your use of Zenova shall be governed by and construed in accordance with the laws of India, without giving effect to conflict of law principles. The competent courts in Bangalore, Karnataka, India shall have exclusive jurisdiction over all claims.
        </p>
      </section>

      {/* 18. Contact Information */}
      <section id="contact" className="space-y-4 p-6 rounded-3xl bg-indigo-950/20 border border-indigo-500/20">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <HelpCircle className="w-5 h-5 text-indigo-400" />
          <span><span className="text-indigo-400">18.</span> Contact Information</span>
        </h2>
        <p className="text-sm leading-relaxed text-slate-300">
          If you have questions, inquiries, or notices regarding these Terms of Service, please reach out to our legal department:
        </p>
        <div className="p-4 rounded-2xl bg-black/40 border border-white/5 text-xs text-slate-300 space-y-1.5 font-mono">
          <div><strong>Entity:</strong> Zenova Platforms / Intellidev Sovereign Systems</div>
          <div><strong>Legal Contact:</strong> <a href="mailto:legal@intellidev.in" className="text-indigo-400 hover:underline">legal@intellidev.in</a></div>
          <div><strong>Website:</strong> <a href="https://www.intellidev.in" className="text-indigo-400 hover:underline">https://www.intellidev.in</a></div>
          <div><strong>Jurisdiction:</strong> Bangalore, Karnataka, India</div>
        </div>
      </section>
    </LegalLayout>
  );
};