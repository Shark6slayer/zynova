import React from 'react';
import { Shield, Lock } from 'lucide-react';

interface LegalLayoutProps {
  title: string;
  subtitle: string;
  lastUpdated: string;
  badgeText: string;
  icon?: React.ReactNode;
  sections: Array<{ id: string; title: string }>;
  children: React.ReactNode;
}

export const LegalLayout: React.FC<LegalLayoutProps> = ({
  title,
  subtitle,
  lastUpdated,
  badgeText,
  icon,
  sections,
  children,
}) => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-purple-500/30 selection:text-purple-200">
      {/* Background radial atmosphere */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-purple-600/10 rounded-full blur-[120px]" />
        <div className="absolute top-1/3 -right-40 w-96 h-96 bg-indigo-600/10 rounded-full blur-[120px]" />
        <div className="absolute -bottom-40 left-1/3 w-96 h-96 bg-rose-600/10 rounded-full blur-[120px]" />
      </div>

      {/* Sticky Top Header */}
      <header className="sticky top-0 z-40 w-full border-b border-white/10 bg-slate-950/80 backdrop-blur-xl transition-all">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <a href="/" className="flex items-center gap-2.5 group">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-rose-500 flex items-center justify-center text-white font-black text-sm shadow-lg shadow-purple-500/20 group-hover:scale-105 transition-transform">
                Z
              </div>
              <span className="text-lg font-black tracking-tight text-white group-hover:text-purple-300 transition-colors">
                ZENOVA
              </span>
            </a>
            <span className="hidden sm:inline-block text-xs font-mono px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-slate-400">
              Legal Center
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs font-medium">
            <a
              href="/privacy-policy"
              className="text-slate-300 hover:text-white transition-colors"
            >
              Privacy Policy
            </a>
            <a
              href="/terms"
              className="text-slate-300 hover:text-white transition-colors"
            >
              Terms of Service
            </a>
            <a
              href="/data-deletion"
              className="hidden sm:inline-block text-slate-400 hover:text-slate-200 transition-colors"
            >
              Data Deletion
            </a>
            <a
              href="/"
              className="px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold transition border border-white/10"
            >
              Open App
            </a>
          </div>
        </div>
      </header>

      {/* Hero Banner */}
      <div className="relative z-10 border-b border-white/10 bg-gradient-to-b from-purple-950/20 to-transparent">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-3 max-w-3xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-semibold uppercase tracking-wider">
                <Shield className="w-3.5 h-3.5" />
                <span>{badgeText}</span>
              </div>
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-white tracking-tight">
                {title}
              </h1>
              <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                {subtitle}
              </p>
              <div className="text-xs text-slate-400 font-mono pt-1">
                Last Updated: <span className="text-slate-200">{lastUpdated}</span>
              </div>
            </div>

            {icon && (
              <div className="hidden lg:flex p-6 rounded-3xl bg-slate-900/60 border border-white/10 shadow-2xl shrink-0">
                {icon}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area: Sidebar TOC + Body */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-16">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-start">
          {/* Table of Contents Sticky Sidebar */}
          <aside className="lg:col-span-4 lg:sticky lg:top-24 space-y-4 order-2 lg:order-1">
            <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl">
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <Lock className="w-3.5 h-3.5 text-purple-400" />
                <span>Table of Contents</span>
              </h2>
              <nav className="space-y-1.5 text-xs">
                {sections.map((section, idx) => (
                  <a
                    key={section.id}
                    href={`#${section.id}`}
                    className="flex items-center gap-2.5 py-1.5 px-2.5 rounded-xl text-slate-300 hover:text-white hover:bg-white/5 transition group"
                  >
                    <span className="text-slate-500 font-mono text-[11px] group-hover:text-purple-400 w-5">
                      {String(idx + 1).padStart(2, '0')}.
                    </span>
                    <span className="truncate">{section.title}</span>
                  </a>
                ))}
              </nav>

              <div className="mt-6 pt-6 border-t border-white/10 space-y-2">
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Have questions about our terms or privacy practices?
                </p>
                <a
                  href="mailto:privacy@intellidev.in"
                  className="inline-block text-xs text-purple-400 hover:text-purple-300 font-semibold"
                >
                  Contact Privacy Team →
                </a>
              </div>
            </div>
          </aside>

          {/* Legal Document Content */}
          <main className="lg:col-span-8 space-y-10 order-1 lg:order-2 leading-relaxed text-slate-200">
            {children}
          </main>
        </div>
      </div>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/10 bg-slate-950 mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-white font-black text-xs">
              Z
            </div>
            <div className="text-xs text-slate-400">
              © {new Date().getFullYear()} Zenova Platforms. All rights reserved. Sovereign Indic Ecosystem.
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 text-xs text-slate-400">
            <a href="/privacy-policy" className="hover:text-white transition">
              Privacy Policy
            </a>
            <a href="/terms" className="hover:text-white transition">
              Terms of Service
            </a>
            <a href="/data-deletion" className="hover:text-white transition">
              Data Deletion
            </a>
            <a href="mailto:privacy@intellidev.in" className="hover:text-white transition">
              Support
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};