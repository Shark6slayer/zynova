import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';
import type { UserPreferences, NavModuleId, AppearanceMode } from '../types';
import { THEME_PRESETS, resolveTheme, type ThemeConfig } from '../design-system/themes';
import { apiClient } from '../services/apiClient';
import { isRtlLanguage } from '../i18n';

interface AppContextType {
  preferences: UserPreferences;
  activeTheme: ThemeConfig;
  isDarkEffective: boolean;
  activeModule: NavModuleId;
  setActiveModule: (module: NavModuleId) => void;
  updatePreferences: (updates: Partial<UserPreferences>) => void;
  resetPreferences: () => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  isCommandPaletteOpen: boolean;
  setIsCommandPaletteOpen: (open: boolean) => void;
  isMobileNavOpen: boolean;
  setIsMobileNavOpen: (open: boolean) => void;
  unreadNotificationsCount: number;
  setUnreadNotificationsCount: (count: number) => void;
  syncPreferencesWithServer: () => Promise<void>;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'midnight-glass',
  appearanceMode: 'system',
  language: 'en',
  accentColor: '#8b5cf6',
  reducedMotion: false,
  fontSize: 'normal',
  compactSidebar: false,
  currency: 'INR',
  aiMemoryEnabled: true,
  pinnedModules: ['home', 'ai-assistant', 'search', 'chat', 'shopping', 'food', 'payments'],
  hiddenModules: [],
  onboardingCompleted: true,
};

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [preferences, setPreferences] = useState<UserPreferences>(() => {
    try {
      const saved = localStorage.getItem('super_ai_prefs');
      if (saved) return { ...DEFAULT_PREFERENCES, ...JSON.parse(saved) };
    } catch (e) {
      console.warn('LocalStorage error reading preferences', e);
    }
    return DEFAULT_PREFERENCES;
  });

  const [activeModule, setActiveModule] = useState<NavModuleId>('home');
  const [searchQuery, setSearchQuery] = useState('');
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState(0);

  // Live system dark mode detection
  const [isSystemDark, setIsSystemDark] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return true;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      setIsSystemDark(e.matches);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handler);
      return () => mediaQuery.removeEventListener('change', handler);
    } else {
      mediaQuery.addListener(handler);
      return () => mediaQuery.removeListener(handler);
    }
  }, []);

  // Compute resolved active theme configuration
  const activeTheme = useMemo(() => {
    const mode = preferences.appearanceMode || 'system';
    return resolveTheme(mode, preferences.theme, isSystemDark, preferences.accentColor);
  }, [preferences.appearanceMode, preferences.theme, isSystemDark, preferences.accentColor]);

  const isDarkEffective = activeTheme.isDark;

  // Apply theme classes and CSS custom properties dynamically to DOM
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;

    // Apply dark / light class to root
    if (isDarkEffective) {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }

    // Apply reduced motion class
    if (preferences.reducedMotion) {
      root.classList.add('reduced-motion');
    } else {
      root.classList.remove('reduced-motion');
    }

    // Apply font scale
    let scale = '1';
    if (preferences.fontSize === 'compact') scale = '0.9';
    if (preferences.fontSize === 'comfortable') scale = '1.08';
    root.style.setProperty('--font-scale', scale);

    // Apply accent color
    const accent = preferences.accentColor || '#8b5cf6';
    root.style.setProperty('--accent-color', accent);
    root.style.setProperty('--accent-glow', `${accent}40`);

    // Dynamic RTL/LTR text direction and lang attribute for Indian languages
    const lang = preferences.language || 'en';
    root.setAttribute('lang', lang);
    const dir = isRtlLanguage(lang) ? 'rtl' : 'ltr';
    root.setAttribute('dir', dir);
  }, [isDarkEffective, preferences.reducedMotion, preferences.fontSize, preferences.accentColor, preferences.language]);

  // Refresh real unread notifications count from backend
  const refreshUnreadCount = async () => {
    if (!apiClient.getToken()) {
      setUnreadNotificationsCount(0);
      return;
    }
    try {
      const count = await apiClient.getUnreadNotificationsCount();
      setUnreadNotificationsCount(count);
    } catch {
      // offline/silent fallback
    }
  };

  // Sync preferences with backend if authenticated
  const syncPreferencesWithServer = async () => {
    if (!apiClient.getToken()) return;
    try {
      const serverPrefs = await apiClient.getPreferences();
      if (serverPrefs && (serverPrefs.theme || serverPrefs.appearanceMode)) {
        setPreferences((prev) => {
          const merged = { ...prev, ...serverPrefs };
          try {
            localStorage.setItem('super_ai_prefs', JSON.stringify(merged));
          } catch {
            // ignore
          }
          return merged;
        });
      }
    } catch {
      // Offline fallback: keep local preferences
    }
  };

  useEffect(() => {
    syncPreferencesWithServer();
    refreshUnreadCount();
    const interval = setInterval(refreshUnreadCount, 15000);
    return () => clearInterval(interval);
  }, []);

  const updatePreferences = (updates: Partial<UserPreferences>) => {
    setPreferences((prev) => {
      const next = { ...prev, ...updates };
      try {
        localStorage.setItem('super_ai_prefs', JSON.stringify(next));
      } catch (e) {
        console.warn('LocalStorage save failed', e);
      }

      // If user is authenticated, persist to MongoDB asynchronously
      if (apiClient.getToken()) {
        apiClient.updatePreferences(next).catch((err) => {
          console.warn('Backend preferences sync error:', err);
        });
      }

      return next;
    });
  };

  const resetPreferences = () => {
    setPreferences(DEFAULT_PREFERENCES);
    try {
      localStorage.removeItem('super_ai_prefs');
    } catch {
      // ignore
    }
    if (apiClient.getToken()) {
      apiClient.updatePreferences(DEFAULT_PREFERENCES).catch(() => {});
    }
  };

  // Keyboard shortcut for Cmd/Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
      if (e.key === 'Escape' && isCommandPaletteOpen) {
        setIsCommandPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isCommandPaletteOpen]);

  return (
    <AppContext.Provider
      value={{
        preferences,
        activeTheme,
        isDarkEffective,
        activeModule,
        setActiveModule,
        updatePreferences,
        resetPreferences,
        searchQuery,
        setSearchQuery,
        isCommandPaletteOpen,
        setIsCommandPaletteOpen,
        isMobileNavOpen,
        setIsMobileNavOpen,
        unreadNotificationsCount,
        setUnreadNotificationsCount,
        syncPreferencesWithServer,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
