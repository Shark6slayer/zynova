import React, { useState } from 'react';
import { 
  Grid, Search, Star, Download, ShieldCheck, 
  Check, ExternalLink, Activity, Train, TrendingUp 
} from 'lucide-react';
import { MOCK_MINI_APPS, type MiniAppItem } from '../../mocks/demoData';

export const MiniAppEcosystemView: React.FC = () => {
  const [apps, setApps] = useState<MiniAppItem[]>(MOCK_MINI_APPS);
  const [activeTab, setActiveTab] = useState<'all' | 'installed'>('all');

  const toggleInstall = (id: string) => {
    setApps((prev) =>
      prev.map((app) => (app.id === id ? { ...app, installed: !app.installed } : app))
    );
  };

  const displayedApps = activeTab === 'installed' ? apps.filter((a) => a.installed) : apps;

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-violet-400 text-xs font-semibold uppercase tracking-wider">
            <Grid className="w-4 h-4" />
            <span>Extensible Mini-App Platform</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Sovereign Mini App Marketplace</h1>
          <p className="text-xs text-slate-400 mt-1">
            Sandboxed micro-applications with strict local permission boundaries and zero tracking.
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-black/40 p-1 rounded-xl border border-white/5 text-xs">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-lg font-medium transition ${
              activeTab === 'all' ? 'bg-violet-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Discover All
          </button>
          <button
            onClick={() => setActiveTab('installed')}
            className={`px-3 py-1.5 rounded-lg font-medium transition ${
              activeTab === 'installed' ? 'bg-violet-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Installed ({apps.filter((a) => a.installed).length})
          </button>
        </div>
      </div>

      {/* Mini Apps Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {displayedApps.map((app) => (
          <div
            key={app.id}
            className="p-5 rounded-2xl border border-white/5 bg-slate-900/40 hover:border-violet-500/30 transition flex flex-col justify-between space-y-4"
          >
            <div className="space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 rounded-xl bg-violet-600/20 text-violet-400 border border-violet-500/30 flex items-center justify-center font-bold">
                    {app.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
                      {app.name}
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    </h4>
                    <p className="text-[11px] text-slate-400">{app.developer}</p>
                  </div>
                </div>

                <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">
                  ★ {app.rating}
                </span>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">{app.description}</p>
            </div>

            <div className="pt-2 border-t border-white/5 flex items-center justify-between">
              <span className="text-[11px] text-slate-500 font-mono">{app.category}</span>
              <button
                onClick={() => toggleInstall(app.id)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition ${
                  app.installed
                    ? 'bg-white/10 text-slate-300 hover:bg-red-500/20 hover:text-red-300'
                    : 'bg-violet-600 hover:bg-violet-500 text-white shadow'
                }`}
              >
                {app.installed ? 'Uninstall' : 'Install Mini-App'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
