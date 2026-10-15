import React, { useState } from 'react';
import { 
  Sparkles, Search, MessageSquare, Utensils, ShoppingBag, 
  CreditCard, Cloud, ArrowUpRight, CheckCircle2, Clock, 
  ChevronRight, TrendingUp, Bell, Calendar, Bot, Share2, Video
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { t } from '../../i18n';
import { MOCK_RESTAURANTS, MOCK_TRANSACTIONS } from '../../mocks/demoData';

export const HomeDashboardView: React.FC = () => {
  const { preferences, activeTheme, setActiveModule } = useApp();
  const [quickInput, setQuickInput] = useState('');

  const handleQuickAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickInput.trim()) return;
    setActiveModule('ai-assistant');
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto w-full">
      {/* Hero Greeting and Universal AI Input */}
      <div className={`relative overflow-hidden rounded-3xl p-6 md:p-8 border ${activeTheme.borderClass} ${activeTheme.surfaceClass} shadow-xl`}>
        <div className="relative z-10 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: preferences.accentColor || '#8b5cf6' }}>
                {new Date().toLocaleDateString(preferences.language === 'en' ? 'en-IN' : preferences.language, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
              </span>
              <h1 className="text-2xl md:text-3xl font-extrabold text-inherit tracking-tight">
                {t('home.greeting_morning', preferences.language, { name: 'Ananya' })}
              </h1>
            </div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                Bengaluru 24°C • Pleasant
              </span>
            </div>
          </div>

          <p className="text-xs md:text-sm text-slate-400 max-w-2xl leading-relaxed">
            {t('home.daily_briefing', preferences.language)}
          </p>

          {/* Quick Universal Input */}
          <form onSubmit={handleQuickAsk} className="relative max-w-2xl mt-4">
            <Bot className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2" style={{ color: preferences.accentColor || '#8b5cf6' }} />
            <input
              type="text"
              value={quickInput}
              onChange={(e) => setQuickInput(e.target.value)}
              placeholder="Ask anything, summon an action, or order lunch..."
              className="w-full pl-12 pr-28 py-3.5 bg-black/10 dark:bg-black/40 border border-white/10 rounded-2xl text-sm text-inherit placeholder-slate-400 focus:outline-none focus:border-violet-500 shadow-inner"
            />
            <button
              type="submit"
              style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 hover:opacity-90 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1 shadow-md"
            >
              <span>Ask AI</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* Ambient Glow Graphic */}
        <div 
          className="absolute -right-20 -bottom-20 w-80 h-80 rounded-full blur-3xl pointer-events-none opacity-20"
          style={{ background: preferences.accentColor || '#8b5cf6' }}
        />
      </div>

      {/* Quick Launch Service Grid (Supported active services only) */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">{t('home.explore_super_ai', preferences.language)}</h3>
          <span className="text-xs font-medium" style={{ color: preferences.accentColor || '#8b5cf6' }}>Unified Sovereign Hub</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {[
            { id: 'search', labelKey: 'nav.search', label: 'Search', icon: Search, color: 'text-violet-400 bg-violet-500/10' },
            { id: 'chat', labelKey: 'nav.chat', label: 'Chat', icon: MessageSquare, color: 'text-emerald-400 bg-emerald-500/10' },
            { id: 'social', labelKey: 'nav.social', label: 'Social', icon: Share2, color: 'text-blue-400 bg-blue-500/10' },
            { id: 'video', labelKey: 'nav.video', label: 'Video', icon: Video, color: 'text-rose-400 bg-rose-500/10' },
            { id: 'shopping', labelKey: 'nav.shopping', label: 'Zaviro', icon: ShoppingBag, color: 'text-pink-400 bg-pink-500/10' },
            { id: 'food', labelKey: 'nav.food', label: 'Food & Dining', icon: Utensils, color: 'text-orange-400 bg-orange-500/10' },
          ].map((item) => {
            const Icon = item.icon;
            const itemLabel = t(item.labelKey, preferences.language) || item.label;
            return (
              <button
                key={item.id}
                onClick={() => setActiveModule(item.id as any)}
                className={`p-4 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} hover:border-violet-500/40 transition-all text-left group flex flex-col justify-between space-y-3 shadow-sm`}
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${item.color} group-hover:scale-105 transition-transform`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-inherit group-hover:opacity-100 opacity-90 transition">{itemLabel}</span>
                  <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Widgets 2-Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 spans): Food & Payments Live Previews */}
        <div className="lg:col-span-2 space-y-6">
          {/* Food Discovery Widget */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-4 shadow-sm`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Utensils className="w-4 h-4 text-orange-400" />
                <h3 className="text-sm font-bold text-inherit">Popular Around Indiranagar</h3>
              </div>
              <button
                onClick={() => setActiveModule('food')}
                className="text-xs hover:underline font-medium flex items-center gap-1"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                View All <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {MOCK_RESTAURANTS.slice(0, 2).map((r) => (
                <div
                  key={r.id}
                  onClick={() => setActiveModule('food')}
                  className="p-3 rounded-xl bg-black/5 dark:bg-slate-800/50 hover:bg-black/10 dark:hover:bg-slate-800 border border-white/5 cursor-pointer transition flex items-center space-x-3"
                >
                  <img src={r.image} alt={r.name} className="w-16 h-16 rounded-lg object-cover shrink-0" />
                  <div className="space-y-0.5 overflow-hidden">
                    <h4 className="text-xs font-semibold text-inherit truncate">{r.name}</h4>
                    <p className="text-[11px] text-slate-400 truncate">{r.popularDish}</p>
                    <div className="flex items-center space-x-2 text-[10px] text-slate-400 pt-1">
                      <span className="text-emerald-400 font-semibold">★ {r.rating}</span>
                      <span>•</span>
                      <span>{r.timeMins} mins</span>
                      <span>•</span>
                      <span>₹{r.priceForTwo} for two</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent UPI Activity */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-4 shadow-sm`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <CreditCard className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-inherit">Recent UPI Transactions</h3>
              </div>
              <button
                onClick={() => setActiveModule('payments')}
                className="text-xs hover:underline font-medium flex items-center gap-1"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                Manage Payments <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-2">
              {MOCK_TRANSACTIONS.slice(0, 3).map((tx) => (
                <div key={tx.id} className="p-3 rounded-xl bg-black/5 dark:bg-slate-800/40 border border-white/5 flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${tx.type === 'credit' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-500/20 text-slate-400'}`}>
                      {tx.type === 'credit' ? '+₹' : '-₹'}
                    </div>
                    <div>
                      <h5 className="font-semibold text-inherit">{tx.title}</h5>
                      <span className="text-[10px] text-slate-400">{tx.timestamp} • {tx.upiId}</span>
                    </div>
                  </div>
                  <span className={`font-semibold ${tx.type === 'credit' ? 'text-emerald-400' : 'text-inherit'}`}>
                    {tx.type === 'credit' ? '+' : '-'}₹{tx.amount.toLocaleString('en-IN')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Sovereign Cloud & Quick Priorities */}
        <div className="space-y-6">
          {/* Cloud Usage Widget */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-3 shadow-sm`}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-inherit flex items-center gap-2">
                <Cloud className="w-4 h-4 text-blue-400" /> Sovereign Cloud
              </h3>
              <button
                onClick={() => setActiveModule('cloud')}
                className="text-xs hover:underline font-medium"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                Drive
              </button>
            </div>
            <p className="text-xs text-slate-400">{t('cloud.storage_used', preferences.language)}</p>
            <div className="w-full bg-black/10 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
              <div 
                className="h-2 rounded-full w-[18.4%]" 
                style={{ background: `linear-gradient(to right, #3b82f6, ${preferences.accentColor || '#8b5cf6'})` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-400 pt-1">
              <span>Local client vault</span>
              <span>Encrypted</span>
            </div>
          </div>

          {/* Quick Priorities */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-3 shadow-sm`}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-inherit flex items-center gap-2">
                <Calendar className="w-4 h-4 text-emerald-400" /> Today's Priorities
              </h3>
              <button
                onClick={() => setActiveModule('notifications')}
                className="text-xs hover:underline font-medium"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                Notifications
              </button>
            </div>
            <div className="space-y-2 text-xs">
              {[
                { task: 'Review Indic language model benchmarks', time: '2:00 PM', done: false },
                { task: 'Explore Zaviro curated electronics catalog', time: '4:30 PM', done: true },
                { task: 'Family dinner reservation at Truffles', time: '7:30 PM', done: false },
              ].map((item, idx) => (
                <div key={idx} className="flex items-center space-x-2.5 p-2 rounded-lg bg-black/5 dark:bg-slate-800/30">
                  <CheckCircle2 className={`w-4 h-4 ${item.done ? 'text-emerald-400' : 'text-slate-400'}`} />
                  <span className={`flex-1 ${item.done ? 'line-through text-slate-400' : 'text-inherit'}`}>
                    {item.task}
                  </span>
                  <span className="text-[10px] text-slate-400">{item.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
