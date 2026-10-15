import React, { useState } from 'react';
import { 
  Search, Bot, Sparkles, Compass, Palette, 
  Utensils, ShoppingBag, CreditCard, ArrowRight, X 
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import type { NavModuleId } from '../../types';

export const CommandPalette: React.FC = () => {
  const { isCommandPaletteOpen, setIsCommandPaletteOpen, setActiveModule, updatePreferences } = useApp();
  const [query, setQuery] = useState('');

  if (!isCommandPaletteOpen) return null;

  const actions: Array<{ title: string; category: string; icon: any; action: () => void }> = [
    { title: 'Open Universal AI Copilot', category: 'Navigation', icon: Bot, action: () => setActiveModule('ai-assistant') },
    { title: 'Universal Web & Research Search', category: 'Navigation', icon: Search, action: () => setActiveModule('search') },
    { title: 'Food & Dining (Indiranagar)', category: 'Lifestyle', icon: Utensils, action: () => setActiveModule('food') },
    { title: 'UPI 2.0 & Payments Ledger', category: 'Finance', icon: CreditCard, action: () => setActiveModule('payments') },
    { title: 'Super Mall ONDC Marketplace', category: 'Shopping', icon: ShoppingBag, action: () => setActiveModule('shopping') },
    { title: 'Global Customization Studio', category: 'System', icon: Palette, action: () => setActiveModule('customization') },
    { title: 'Switch to Midnight Glass Theme', category: 'Theme', icon: Palette, action: () => updatePreferences({ theme: 'midnight-glass' }) },
    { title: 'Switch to Indian Heritage Theme', category: 'Theme', icon: Palette, action: () => updatePreferences({ theme: 'indian-heritage' }) },
    { title: 'Switch to Aurora Dark Theme', category: 'Theme', icon: Palette, action: () => updatePreferences({ theme: 'aurora-dark' }) },
  ];

  const filtered = actions.filter((a) =>
    a.title.toLowerCase().includes(query.toLowerCase()) || a.category.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div 
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-black/80 backdrop-blur-md"
      onClick={() => setIsCommandPaletteOpen(false)}
    >
      <div 
        className="w-full max-w-xl rounded-2xl bg-slate-900 border border-violet-500/30 overflow-hidden shadow-2xl space-y-2"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Field */}
        <div className="p-3.5 border-b border-white/10 flex items-center space-x-3">
          <Search className="w-5 h-5 text-violet-400 shrink-0" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command, module name, or theme (Esc to exit)..."
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
          />
          <button
            onClick={() => setIsCommandPaletteOpen(false)}
            className="p-1 text-slate-500 hover:text-white rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">No matching commands or destinations found.</div>
          ) : (
            filtered.map((item, idx) => {
              const Icon = item.icon;
              return (
                <div
                  key={idx}
                  onClick={() => {
                    item.action();
                    setIsCommandPaletteOpen(false);
                  }}
                  className="p-2.5 rounded-xl hover:bg-violet-600/20 hover:border-violet-500/30 border border-transparent cursor-pointer transition flex items-center justify-between text-xs"
                >
                  <div className="flex items-center space-x-3">
                    <Icon className="w-4 h-4 text-violet-400 shrink-0" />
                    <span className="font-medium text-slate-200">{item.title}</span>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">{item.category}</span>
                </div>
              );
            })
          )}
        </div>

        <div className="p-2.5 px-4 bg-black/40 border-t border-white/5 flex items-center justify-between text-[11px] text-slate-500">
          <span>Navigate with mouse or click</span>
          <span className="font-mono">SUPER_AI v2.0</span>
        </div>
      </div>
    </div>
  );
};
