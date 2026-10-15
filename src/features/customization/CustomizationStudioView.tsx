import React, { useState, useRef } from 'react';
import { 
  Palette, Type, Globe, RefreshCcw, 
  Check, Download, Upload, Sparkles, AlertCircle,
  Sun, Moon, Laptop
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { THEME_PRESETS, ACCENT_COLORS } from '../../design-system/themes';
import { SUPPORTED_LOCALES_LIST } from '../../i18n';
import type { ThemePreset, AppLanguage, UserPreferences, AppearanceMode } from '../../types';

export const CustomizationStudioView: React.FC = () => {
  const { preferences, updatePreferences, resetPreferences } = useApp();
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentMode = preferences.appearanceMode || 'system';

  const handleExportJSON = () => {
    try {
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(preferences, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute('href', dataStr);
      downloadAnchor.setAttribute('download', 'super_ai_theme_backup.json');
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      setNotification({ message: 'Customization profile exported as valid JSON.', type: 'success' });
      setTimeout(() => setNotification(null), 3000);
    } catch {
      setNotification({ message: 'Failed to export configuration.', type: 'error' });
      setTimeout(() => setNotification(null), 3000);
    }
  };

  const handleImportJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string) as Partial<UserPreferences>;
        if (parsed && typeof parsed === 'object') {
          updatePreferences(parsed);
          setNotification({ message: 'Custom theme profile imported and applied successfully!', type: 'success' });
        } else {
          setNotification({ message: 'Invalid configuration file format.', type: 'error' });
        }
      } catch {
        setNotification({ message: 'Could not parse JSON configuration file.', type: 'error' });
      }
      setTimeout(() => setNotification(null), 3500);
    };
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full pb-10">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-violet-400 text-xs font-semibold uppercase tracking-wider">
            <Palette className="w-4 h-4" />
            <span>Theme & Interface Engine</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Global Customization Studio</h1>
          <p className="text-xs text-slate-400 mt-1">
            Tailor appearance modes, accent colors, typography, regional languages, and dashboard density.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleImportJSON}
            accept=".json,application/json"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-medium border border-white/10 transition flex items-center gap-1.5"
            title="Import Saved Configuration JSON"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Import</span>
          </button>
          <button
            onClick={resetPreferences}
            className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-medium border border-white/10 transition flex items-center gap-1.5"
          >
            <RefreshCcw className="w-3.5 h-3.5" />
            <span>Reset Defaults</span>
          </button>
          <button
            onClick={handleExportJSON}
            className="px-4 py-2 rounded-xl text-white text-xs font-semibold transition shadow-md flex items-center gap-1.5"
            style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Config</span>
          </button>
        </div>
      </div>

      {notification && (
        <div className={`p-3 rounded-xl border text-xs flex items-center gap-2 ${
          notification.type === 'success' 
            ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300' 
            : 'bg-red-500/20 border-red-500/30 text-red-300'
        }`}>
          {notification.type === 'success' ? <Check className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Appearance Modes (System / Light / Dark) */}
      <div className="p-6 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
        <div className="flex items-center space-x-2">
          <Sun className="w-5 h-5 text-amber-400" />
          <h3 className="text-base font-bold text-white">Appearance Mode</h3>
        </div>
        <p className="text-xs text-slate-400">
          Select whether SUPER_AI follows your operating system appearance or forces a dedicated light or dark theme.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
          {[
            { id: 'system', label: 'System Automatic', desc: 'Syncs automatically with device OS dark mode', icon: Laptop },
            { id: 'light', label: 'Light Mode', desc: 'High-clarity light canvas with crisp slate borders', icon: Sun },
            { id: 'dark', label: 'Dark Mode', desc: 'OLED-optimized deep charcoal with low glare', icon: Moon },
          ].map((item) => {
            const isSelected = currentMode === item.id;
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => updatePreferences({ appearanceMode: item.id as AppearanceMode })}
                className={`p-4 rounded-2xl border text-left transition-all flex items-start space-x-3 ${
                  isSelected
                    ? 'border-violet-500 bg-violet-600/20 text-white font-semibold ring-2 ring-violet-500/20'
                    : 'border-white/5 bg-slate-800/40 text-slate-300 hover:bg-slate-800'
                }`}
              >
                <div className="p-2 rounded-xl bg-white/10 shrink-0">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold flex items-center justify-between">
                    <span>{item.label}</span>
                    {isSelected && <Check className="w-4 h-4 text-violet-400 ml-2" />}
                  </div>
                  <div className="text-xs text-slate-400 mt-1 leading-relaxed">{item.desc}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* User-Selectable Accent Color Palette */}
      <div className="p-6 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
        <div className="flex items-center space-x-2">
          <Palette className="w-5 h-5 text-violet-400" />
          <h3 className="text-base font-bold text-white">Interactive Accent Color</h3>
        </div>
        <p className="text-xs text-slate-400">
          Personalize active highlights, glow effects, badges, and primary buttons across all 10 unified modules.
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 pt-1">
          {ACCENT_COLORS.map((col) => {
            const isSelected = preferences.accentColor === col.hex;
            return (
              <button
                key={col.id}
                onClick={() => updatePreferences({ accentColor: col.hex })}
                className={`p-3 rounded-2xl border transition-all flex flex-col items-center justify-center space-y-2 ${
                  isSelected 
                    ? 'border-white ring-2 ring-white/30 bg-white/10 shadow-lg' 
                    : 'border-white/5 bg-slate-800/40 hover:bg-slate-800'
                }`}
              >
                <div 
                  className="w-8 h-8 rounded-full shadow-md flex items-center justify-center text-white"
                  style={{ backgroundColor: col.hex }}
                >
                  {isSelected && <Check className="w-4 h-4" />}
                </div>
                <span className="text-xs font-semibold text-slate-200 text-center">{col.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Visual Presets Selector */}
      <div className="space-y-3">
        <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          Curated Design Presets (6 Distinct Aesthetics)
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {(Object.keys(THEME_PRESETS) as ThemePreset[]).map((presetKey) => {
            const p = THEME_PRESETS[presetKey];
            const isSelected = preferences.theme === presetKey;

            return (
              <div
                key={presetKey}
                onClick={() => updatePreferences({ theme: presetKey })}
                className={`p-4 rounded-2xl border cursor-pointer transition-all relative overflow-hidden group ${
                  isSelected ? 'border-violet-500 ring-2 ring-violet-500/20 shadow-lg' : 'border-white/10 hover:border-white/20'
                } ${p.surfaceClass}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-sm font-bold ${p.textClass}`}>{p.name}</span>
                  {isSelected && (
                    <span className="w-5 h-5 rounded-full bg-violet-600 text-white flex items-center justify-center text-xs">
                      <Check className="w-3.5 h-3.5" />
                    </span>
                  )}
                </div>
                <p className={`text-xs ${p.mutedClass} line-clamp-2 leading-relaxed`}>{p.description}</p>

                {/* Swatch Previews */}
                <div className="flex items-center space-x-1.5 mt-4 pt-3 border-t border-white/5">
                  <div className={`w-4 h-4 rounded-full ${p.bgClass} border border-white/20`} />
                  <div className={`w-4 h-4 rounded-full ${p.accentClass}`} />
                  <div className="w-4 h-4 rounded-full bg-white/20 backdrop-blur-sm" />
                  <span className="text-[10px] text-slate-400 pl-1">{p.isDark ? 'Dark Mode' : 'Light Mode'}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Multilingual and Regional Settings */}
      <div className="p-6 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
        <div className="flex items-center space-x-2">
          <Globe className="w-5 h-5 text-indigo-400" />
          <h3 className="text-base font-bold text-white">India-First Language & Formatting</h3>
        </div>
        <p className="text-xs text-slate-400">
          SUPER_AI features architectural support for all 22 languages listed in the Eighth Schedule of the Constitution of India.
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5 pt-2 max-h-72 overflow-y-auto pr-1">
          {SUPPORTED_LOCALES_LIST.map((lang) => {
            const isSelected = preferences.language === lang.code;
            return (
              <button
                key={lang.code}
                onClick={() => updatePreferences({ language: lang.code as AppLanguage })}
                className={`p-3 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
                  isSelected
                    ? 'border-violet-500 bg-violet-600/20 text-white font-semibold ring-1 ring-violet-500/30'
                    : 'border-white/5 bg-slate-800/40 text-slate-300 hover:bg-slate-800'
                }`}
              >
                <div>
                  <div className="text-sm font-bold">{lang.nativeName}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{lang.name}</div>
                </div>
                <div className="flex items-center gap-1 mt-2 text-[9px] font-mono text-slate-400">
                  <span className="px-1 py-0.5 rounded bg-white/5">{lang.script}</span>
                  {lang.direction === 'rtl' && (
                    <span className="px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">RTL</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Typography and Density */}
      <div className="p-6 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
        <div className="flex items-center space-x-2">
          <Type className="w-5 h-5 text-pink-400" />
          <h3 className="text-base font-bold text-white">Typography Scale & UI Density</h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { id: 'compact', label: 'Compact', desc: 'Higher data density, ideal for dashboards' },
            { id: 'normal', label: 'Balanced (Standard)', desc: 'Optimized readability and rhythm' },
            { id: 'comfortable', label: 'Comfortable', desc: 'Spacious padding for touch and leisure' },
          ].map((dens) => {
            const isSelected = preferences.fontSize === dens.id;
            return (
              <button
                key={dens.id}
                onClick={() => updatePreferences({ fontSize: dens.id as any })}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  isSelected
                    ? 'border-violet-500 bg-violet-600/20 text-white font-semibold'
                    : 'border-white/5 bg-slate-800/40 text-slate-300 hover:bg-slate-800'
                }`}
              >
                <div className="text-sm font-semibold">{dens.label}</div>
                <div className="text-xs text-slate-400 mt-1">{dens.desc}</div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
