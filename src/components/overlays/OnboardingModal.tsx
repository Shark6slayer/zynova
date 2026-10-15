import React, { useState } from 'react';
import { 
  Bot, Globe, Palette, Sparkles, Check, ArrowRight, ShieldCheck 
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { THEME_PRESETS } from '../../design-system/themes';
import { SUPPORTED_LOCALES_LIST } from '../../i18n';
import type { ThemePreset, AppLanguage } from '../../types';

export const OnboardingModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { preferences, updatePreferences } = useApp();
  const [step, setStep] = useState(1);

  const handleFinish = () => {
    updatePreferences({ onboardingCompleted: true });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="w-full max-w-xl rounded-3xl bg-slate-900 border border-violet-500/30 p-6 md:p-8 space-y-6 shadow-2xl relative overflow-hidden">
        {/* Glow */}
        <div className="absolute -top-24 -right-24 w-60 h-60 rounded-full bg-violet-600/20 blur-3xl pointer-events-none" />

        {/* Step 1: Welcome */}
        {step === 1 && (
          <div className="space-y-4 text-center">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center text-white mx-auto shadow-lg">
              <Sparkles className="w-7 h-7" />
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">Welcome to SUPER_AI</h2>
            <p className="text-xs text-slate-300 leading-relaxed max-w-md mx-auto">
              India's first intelligent AI Super App unifying dining, UPI payments, messaging, search, video, and personal productivity into one sovereign interface.
            </p>

            <div className="pt-4">
              <button
                onClick={() => setStep(2)}
                className="px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition shadow-lg inline-flex items-center gap-1.5"
              >
                <span>Personalize Experience</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Language & Region */}
        {step === 2 && (
          <div className="space-y-4">
            <div className="flex items-center space-x-2 text-indigo-400 text-xs font-semibold uppercase">
              <Globe className="w-4 h-4" />
              <span>Step 2 of 3: Choose Primary Language</span>
            </div>
            <h3 className="text-lg font-bold text-white">Select Your Native Interface Language</h3>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 max-h-60 overflow-y-auto pr-1">
              {SUPPORTED_LOCALES_LIST.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => updatePreferences({ language: lang.code as AppLanguage })}
                  className={`p-2.5 rounded-xl border text-left transition ${
                    preferences.language === lang.code
                      ? 'border-violet-500 bg-violet-600/25 text-white font-bold ring-1 ring-violet-500/50'
                      : 'border-white/5 bg-slate-800/40 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <div className="text-xs font-bold leading-tight">{lang.nativeName}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{lang.name}</div>
                </button>
              ))}
            </div>

            <div className="flex justify-between items-center pt-4">
              <button onClick={() => setStep(1)} className="text-xs text-slate-400 hover:text-white">
                Back
              </button>
              <button
                onClick={() => setStep(3)}
                className="px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition shadow"
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Aesthetic Theme */}
        {step === 3 && (
          <div className="space-y-4">
            <div className="flex items-center space-x-2 text-violet-400 text-xs font-semibold uppercase">
              <Palette className="w-4 h-4" />
              <span>Step 3 of 3: Visual Theme</span>
            </div>
            <h3 className="text-lg font-bold text-white">Choose Your Ambient Interface Aesthetic</h3>

            <div className="grid grid-cols-2 gap-3 pt-1">
              {(['midnight-glass', 'aurora-dark', 'indian-heritage', 'cyber-violet'] as ThemePreset[]).map((themeKey) => {
                const theme = THEME_PRESETS[themeKey];
                return (
                  <button
                    key={themeKey}
                    onClick={() => updatePreferences({ theme: themeKey })}
                    className={`p-3 rounded-xl border text-left transition ${
                      preferences.theme === themeKey
                        ? 'border-violet-500 bg-violet-600/20 text-white font-bold'
                        : 'border-white/5 bg-slate-800/40 text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    <div className="text-xs font-semibold">{theme.name}</div>
                    <div className="text-[10px] text-slate-400 mt-1 line-clamp-1">{theme.description}</div>
                  </button>
                );
              })}
            </div>

            <div className="flex justify-between items-center pt-4">
              <button onClick={() => setStep(2)} className="text-xs text-slate-400 hover:text-white">
                Back
              </button>
              <button
                onClick={handleFinish}
                className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition shadow-lg flex items-center gap-1.5"
              >
                <Check className="w-4 h-4" />
                <span>Enter SUPER_AI</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
