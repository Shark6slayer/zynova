import type { ThemePreset, AppearanceMode } from '../types';

export interface ThemeConfig {
  id: ThemePreset;
  name: string;
  description: string;
  isDark: boolean;
  bgClass: string;
  surfaceClass: string;
  borderClass: string;
  textClass: string;
  mutedClass: string;
  accentClass: string;
  accentGlow: string;
  glassStyle: string;
}

export const THEME_PRESETS: Record<ThemePreset, ThemeConfig> = {
  'midnight-glass': {
    id: 'midnight-glass',
    name: 'Midnight Glass (Default)',
    description: 'Sleek deep charcoal with electric violet accents & frosted glass',
    isDark: true,
    bgClass: 'bg-[#090b10]',
    surfaceClass: 'bg-[#121620]/80 backdrop-blur-md',
    borderClass: 'border-white/10',
    textClass: 'text-slate-100',
    mutedClass: 'text-slate-400',
    accentClass: 'text-violet-400 bg-violet-600',
    accentGlow: 'rgba(139, 92, 246, 0.25)',
    glassStyle: 'rgba(18, 22, 32, 0.75)',
  },
  'aurora-dark': {
    id: 'aurora-dark',
    name: 'Aurora Dark',
    description: 'Boreal emerald & cyan over dark indigo atmosphere',
    isDark: true,
    bgClass: 'bg-[#070e17]',
    surfaceClass: 'bg-[#0d1b2a]/80 backdrop-blur-md',
    borderClass: 'border-cyan-500/20',
    textClass: 'text-slate-100',
    mutedClass: 'text-cyan-300/60',
    accentClass: 'text-emerald-400 bg-emerald-600',
    accentGlow: 'rgba(16, 185, 129, 0.25)',
    glassStyle: 'rgba(13, 27, 42, 0.75)',
  },
  'minimal-light': {
    id: 'minimal-light',
    name: 'Minimal Light',
    description: 'Clean crisp modern light palette with slate elevation',
    isDark: false,
    bgClass: 'bg-[#f8fafc]',
    surfaceClass: 'bg-white/95 backdrop-blur-md shadow-sm',
    borderClass: 'border-slate-200',
    textClass: 'text-slate-900',
    mutedClass: 'text-slate-500',
    accentClass: 'text-indigo-600 bg-indigo-600',
    accentGlow: 'rgba(99, 102, 241, 0.15)',
    glassStyle: 'rgba(255, 255, 255, 0.92)',
  },
  'monochrome': {
    id: 'monochrome',
    name: 'Monochrome High-Contrast',
    description: 'Pure black & titanium white with stark precision',
    isDark: true,
    bgClass: 'bg-[#000000]',
    surfaceClass: 'bg-[#111111]/90 backdrop-blur-md',
    borderClass: 'border-white/20',
    textClass: 'text-white',
    mutedClass: 'text-zinc-400',
    accentClass: 'text-white bg-zinc-200 text-black',
    accentGlow: 'rgba(255, 255, 255, 0.2)',
    glassStyle: 'rgba(17, 17, 17, 0.9)',
  },
  'indian-heritage': {
    id: 'indian-heritage',
    name: 'Indian Heritage',
    description: 'Rich royal saffron, peacock blue & warm sandalwood accents',
    isDark: true,
    bgClass: 'bg-[#0c0906]',
    surfaceClass: 'bg-[#1a130b]/85 backdrop-blur-md',
    borderClass: 'border-amber-500/20',
    textClass: 'text-amber-50',
    mutedClass: 'text-amber-200/60',
    accentClass: 'text-amber-400 bg-gradient-to-r from-amber-600 to-orange-500',
    accentGlow: 'rgba(245, 158, 11, 0.25)',
    glassStyle: 'rgba(26, 19, 11, 0.85)',
  },
  'cyber-violet': {
    id: 'cyber-violet',
    name: 'Cyber Violet Neon',
    description: 'Deep abyss with vibrant electric purple & hot pink radiance',
    isDark: true,
    bgClass: 'bg-[#090514]',
    surfaceClass: 'bg-[#160d2e]/85 backdrop-blur-md',
    borderClass: 'border-fuchsia-500/25',
    textClass: 'text-fuchsia-50',
    mutedClass: 'text-purple-300/60',
    accentClass: 'text-fuchsia-400 bg-fuchsia-600',
    accentGlow: 'rgba(217, 70, 239, 0.3)',
    glassStyle: 'rgba(22, 13, 46, 0.85)',
  },
};

export const ACCENT_COLORS = [
  { id: 'violet', name: 'Electric Violet', hex: '#8b5cf6', rgb: '139, 92, 246' },
  { id: 'blue', name: 'Sapphire Blue', hex: '#3b82f6', rgb: '59, 130, 246' },
  { id: 'emerald', name: 'Boreal Emerald', hex: '#10b981', rgb: '16, 185, 129' },
  { id: 'amber', name: 'Royal Saffron', hex: '#f59e0b', rgb: '245, 158, 11' },
  { id: 'rose', name: 'Crimson Rose', hex: '#f43f5e', rgb: '244, 63, 94' },
  { id: 'cyan', name: 'Cyber Cyan', hex: '#06b6d4', rgb: '6, 182, 212' },
];

/**
 * Resolves the effective theme configuration taking into account
 * AppearanceMode ('system' | 'light' | 'dark'), chosen preset, and custom accent color.
 */
export function resolveTheme(
  appearanceMode: AppearanceMode = 'system',
  preset: ThemePreset = 'midnight-glass',
  isSystemDark: boolean = true,
  customAccentColor?: string
): ThemeConfig {
  let effectiveIsDark = isSystemDark;
  if (appearanceMode === 'light') {
    effectiveIsDark = false;
  } else if (appearanceMode === 'dark') {
    effectiveIsDark = true;
  }

  let baseTheme = THEME_PRESETS[preset] || THEME_PRESETS['midnight-glass'];

  // If appearance mode forces light mode and the chosen preset is dark, switch to minimal-light
  if (!effectiveIsDark && baseTheme.isDark) {
    baseTheme = THEME_PRESETS['minimal-light'];
  } else if (effectiveIsDark && !baseTheme.isDark) {
    // If appearance mode forces dark mode and chosen preset is minimal-light, switch to midnight-glass
    baseTheme = THEME_PRESETS['midnight-glass'];
  }

  if (customAccentColor) {
    return {
      ...baseTheme,
      accentGlow: `${customAccentColor}40`,
    };
  }

  return baseTheme;
}
