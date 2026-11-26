import React, { useEffect } from 'react';
import { ArrowLeft, Shield } from 'lucide-react';

interface LegalPageLayoutProps {
  title: string;
  description: string;
  canonicalPath: string;
  subtitle?: string;
  icon?: React.ReactNode;
  iconBgClass?: string;
  children: React.ReactNode;
}

const LEGAL_NAV_LINKS = [
  { label: 'Privacy Policy', href: '/privacy-policy' },
  { label: 'Terms of Service', href: '/terms' },
  { label: 'Child Safety', href: '/child-safety' },
  { label: 'Community Guidelines', href: '/community-guidelines' },
  { label: 'Content Moderation', href: '/content-moderation' },
  { label: 'Safety Center', href: '/safety' },
  { label: 'Data Rights', href: '/data-rights' },
  { label: 'Delete Account', href: '/delete-account' },
  { label: 'Contact Support', href: '/contact' },
];

export const LegalPageLayout: React.FC<LegalPageLayoutProps> = ({
  title,
  description,
  canonicalPath,
  subtitle,
  icon,
  iconBgClass = 'bg-purple-500/10 border-purple-500/20 text-purple-400',
  children,
}) => {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${title} — ZENOVA`;

    let metaDesc = document.querySelector('meta[name="description"]') as HTMLMetaElement | null;
    const createdDesc = !metaDesc;
    if (!metaDesc) {
      metaDesc = document.createElement('meta');
      metaDesc.name = 'description';
      document.head.appendChild(metaDesc);
    }
    const previousDesc = metaDesc.content;
    metaDesc.content = description;

    let canonicalLink = document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null;
    const createdCanonical = !canonicalLink;
    if (!canonicalLink) {
      canonicalLink = document.createElement('link');
      canonicalLink.rel = 'canonical';
      document.head.appendChild(canonicalLink);
    }
    const previousCanonical = canonicalLink.href;
    canonicalLink.href = `https://www.intellidev.in${canonicalPath}`;

    return () => {
      document.title = previousTitle;
      if (metaDesc) {
        if (createdDesc) metaDesc.remove();
        else metaDesc.content = previousDesc;
      }
      if (canonicalLink) {
        if (createdCanonical) canonicalLink.remove();
        else canonicalLink.href = previousCanonical;
      }
    };
  }, [title, description, canonicalPath]);

  const currentPath =
    typeof window !== 'undefined'
      ? window.location.pathname.replace(/\/+$/, '') || '/'
      : canonicalPath;

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col font-sans selection:bg-purple-500/30">
      {/* Top Bar */}
      <header className="border-b border-white/10 bg-slate-950/90 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 md:px-8 h-14 flex items-center justify-between gap-4">
          <a
            href="/"
            className="inline-flex items-center gap-2 text-xs sm:text-sm text-purple-400 hover:text-purple-300 font-semibold transition focus:outline-none focus:ring-2 focus:ring-purple-500 rounded-lg px-2 py-1 -ml-2"
          >
            <ArrowLeft className="w-4 h-4 shrink-0" />
            <span>Back to ZENOVA</span>
          </a>
          <nav aria-label="Quick Legal Links" className="hidden sm:flex items-center gap-4 text-xs text-slate-400">
            <a href="/privacy-policy" className="hover:text-white transition">Privacy</a>
            <a href="/terms" className="hover:text-white transition">Terms</a>
            <a href="/child-safety" className="hover:text-white transition">Child Safety</a>
            <a href="/safety" className="hover:text-white transition">Safety</a>
            <a href="/contact" className="hover:text-white transition">Contact</a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-6 md:px-8 py-8 md:py-12 space-y-8">
        <div className="flex items-start sm:items-center justify-between gap-4 border-b border-white/10 pb-6">
          <div className="space-y-1.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              {title}
            </h1>
            {subtitle && (
              <p className="text-xs sm:text-sm text-slate-400">{subtitle}</p>
            )}
          </div>
          <div className={`p-3 border rounded-2xl shrink-0 ${iconBgClass}`} aria-hidden="true">
            {icon || <Shield className="w-6 h-6" />}
          </div>
        </div>

        <div className="space-y-8">{children}</div>
      </main>

      {/* Legal Footer Navigation */}
      <footer className="border-t border-white/10 bg-slate-900/50 mt-auto">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 md:px-8 py-8 space-y-6">
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              ZENOVA Legal, Safety &amp; Trust Center
            </h2>
            <nav aria-label="Legal and Safety Navigation" className="flex flex-wrap gap-x-5 gap-y-2.5">
              {LEGAL_NAV_LINKS.map((link) => {
                const isActive = currentPath === link.href;
                return (
                  <a
                    key={link.href}
                    href={link.href}
                    aria-current={isActive ? 'page' : undefined}
                    className={`text-xs transition underline-offset-4 hover:underline ${
                      isActive
                        ? 'text-purple-400 font-semibold'
                        : 'text-slate-300 hover:text-white'
                    }`}
                  >
                    {link.label}
                  </a>
                );
              })}
            </nav>
          </div>

          <div className="pt-4 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-500">
            <p>&copy; {new Date().getFullYear()} ZENOVA / Intellidev Sovereign Systems. All rights reserved.</p>
            <p>
              Official Website:{' '}
              <a
                href="https://www.intellidev.in"
                target="_blank"
                rel="noreferrer"
                className="text-purple-400 hover:text-purple-300 underline"
              >
                https://www.intellidev.in
              </a>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};
