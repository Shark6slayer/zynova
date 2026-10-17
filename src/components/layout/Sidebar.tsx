import React, { useEffect, useRef } from 'react';
import { 
  Home, Search, MessageSquare, Share2, Video, 
  Utensils, ShoppingBag, CreditCard, Bell, Settings, 
  ChevronLeft, ChevronRight, Sparkles, Sun, Moon, Laptop,
  X, User, ShieldCheck
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import type { NavModuleId, AppearanceMode } from '../../types';
import { t } from '../../i18n';
import { MOCK_USER } from '../../mocks/demoData';

interface NavItem {
  id: NavModuleId;
  label: string;
  labelKey: string;
  icon: any;
  category: 'core' | 'connect' | 'lifestyle' | 'system';
  badge?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'home', label: 'Home', labelKey: 'nav.home', icon: Home, category: 'core' },
  { id: 'search', label: 'Search', labelKey: 'nav.search', icon: Search, category: 'core' },
  { id: 'chat', label: 'Chat', labelKey: 'nav.chat', icon: MessageSquare, category: 'connect', badge: '3' },
  { id: 'social', label: 'Social', labelKey: 'nav.social', icon: Share2, category: 'connect' },
  { id: 'video', label: 'Video', labelKey: 'nav.video', icon: Video, category: 'connect' },
  { id: 'shopping', label: 'Zaviro', labelKey: 'nav.shopping', icon: ShoppingBag, category: 'lifestyle' },
  { id: 'food', label: 'Food & Dining', labelKey: 'nav.food', icon: Utensils, category: 'lifestyle' },
  { id: 'payments', label: 'Payments', labelKey: 'nav.payments', icon: CreditCard, category: 'lifestyle' },
  { id: 'notifications', label: 'Notifications', labelKey: 'nav.notifications', icon: Bell, category: 'system' },
  { id: 'settings', label: 'Settings', labelKey: 'nav.settings', icon: Settings, category: 'system' },
];

interface SidebarProps {
  isMobileDrawer?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isMobileDrawer = false, onCloseMobile }) => {
  const { 
    activeModule, 
    setActiveModule, 
    preferences, 
    updatePreferences, 
    activeTheme, 
    unreadNotificationsCount 
  } = useApp();
  const { user, isAuthenticated, openLoginModal } = useAuth();
  const sidebarRef = useRef<HTMLElement>(null);

  const isCompact = !isMobileDrawer && preferences.compactSidebar;

  const handleNavClick = (id: NavModuleId) => {
    setActiveModule(id);
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  const handleAppearanceToggle = (mode: AppearanceMode) => {
    updatePreferences({ appearanceMode: mode });
  };

  // Keyboard navigation & accessibility in mobile drawer
  useEffect(() => {
    if (!isMobileDrawer) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onCloseMobile) {
        onCloseMobile();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMobileDrawer, onCloseMobile]);

  const displayedName = user?.full_name || MOCK_USER.name;
  const displayedAvatar = user?.avatar_url || MOCK_USER.avatar;
  const currentAppearance = preferences.appearanceMode || 'system';

  return (
    <aside
      ref={sidebarRef}
      role="navigation"
      aria-label="Main Application Navigation"
      className={`h-full border-r ${activeTheme.borderClass} ${activeTheme.surfaceClass} flex flex-col justify-between transition-all duration-300 z-30 shrink-0 select-none ${
        isMobileDrawer ? 'w-72 shadow-2xl' : isCompact ? 'w-[68px]' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex flex-col min-h-0 flex-1">
        <div className={`p-3.5 border-b ${activeTheme.borderClass} flex items-center justify-between`}>
          {(!isCompact || isMobileDrawer) && (
            <div 
              onClick={() => handleNavClick('home')}
              className="flex items-center space-x-2.5 cursor-pointer group"
            >
              <div 
                className="w-8 h-8 rounded-xl flex items-center justify-center text-white shadow-md transition-transform group-hover:scale-105"
                style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
              >
                <Sparkles className="w-4 h-4" />
              </div>
              <div className="overflow-hidden">
                <span className="font-extrabold text-sm tracking-wider text-inherit block leading-none">ZYNOVA</span>
                <span className="text-[9px] font-mono tracking-tight text-slate-400 block mt-0.5">UNIFIED PLATFORM</span>
              </div>
            </div>
          )}

          {isCompact && !isMobileDrawer && (
            <div 
              onClick={() => handleNavClick('home')}
              className="mx-auto w-8 h-8 rounded-xl flex items-center justify-center text-white shadow-md cursor-pointer transition-transform hover:scale-105"
              style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
              title="Zynova Home"
            >
              <Sparkles className="w-4 h-4" />
            </div>
          )}

          {/* Desktop Collapse / Expand Toggle */}
          {!isMobileDrawer && (
            <button
              onClick={() => updatePreferences({ compactSidebar: !isCompact })}
              aria-label={isCompact ? 'Expand sidebar' : 'Collapse sidebar'}
              className="hidden md:flex p-1.5 rounded-lg hover:bg-black/10 dark:hover:bg-white/10 text-slate-400 hover:text-inherit transition"
              title={isCompact ? 'Expand Sidebar' : 'Collapse Sidebar'}
            >
              {isCompact ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          )}

          {/* Mobile Drawer Close Button */}
          {isMobileDrawer && (
            <button
              onClick={onCloseMobile}
              aria-label="Close menu drawer"
              className="p-1.5 rounded-xl hover:bg-black/10 dark:hover:bg-white/10 text-slate-400 hover:text-inherit transition"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Navigation Items List */}
        <nav className="p-2 space-y-1 overflow-y-auto flex-1 focus:outline-none">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeModule === item.id;
            const itemLabel = t(item.labelKey, preferences.language) || item.label;

            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                aria-current={isActive ? 'page' : undefined}
                title={isCompact && !isMobileDrawer ? itemLabel : undefined}
                className={`w-full flex items-center rounded-xl px-3 py-2.5 text-xs font-semibold transition-all group relative ${
                  isActive
                    ? 'text-white font-bold shadow-md'
                    : 'text-slate-400 hover:text-inherit hover:bg-black/5 dark:hover:bg-white/5'
                } ${isCompact && !isMobileDrawer ? 'justify-center px-0' : 'space-x-3'}`}
                style={isActive ? { backgroundColor: preferences.accentColor || '#8b5cf6' } : undefined}
              >
                <Icon className={`w-4 h-4 shrink-0 transition-transform ${isActive ? 'scale-110 text-white' : 'group-hover:scale-105'}`} />

                {(!isCompact || isMobileDrawer) && (
                  <span className="truncate flex-1 text-left">
                    {itemLabel}
                  </span>
                )}

                {(!isCompact || isMobileDrawer) && (item.badge || (item.id === 'notifications' && unreadNotificationsCount > 0)) && (
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono shrink-0 ${
                      isActive
                        ? 'bg-white/90 text-slate-900 font-bold'
                        : 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                    }`}
                  >
                    {item.id === 'notifications' ? unreadNotificationsCount : item.badge}
                  </span>
                )}

                {/* Compact tooltip preview on hover */}
                {isCompact && !isMobileDrawer && (
                  <span className="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-[11px] rounded-lg shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition whitespace-nowrap z-50 border border-white/10">
                    {itemLabel}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Controls: Quick Theme Mode & Account Profile */}
      <div className={`p-2.5 border-t ${activeTheme.borderClass} space-y-2`}>
        {/* Appearance Mode Segmented Control (System / Light / Dark) */}
        {(!isCompact || isMobileDrawer) ? (
          <div className="flex items-center justify-between p-1 bg-black/10 dark:bg-black/40 rounded-xl border border-white/5 text-[11px]">
            <button
              onClick={() => handleAppearanceToggle('system')}
              aria-label="System Theme"
              className={`flex-1 py-1 px-1.5 rounded-lg flex items-center justify-center gap-1 transition ${
                currentAppearance === 'system' ? 'bg-white/20 dark:bg-white/15 text-inherit font-bold shadow-sm' : 'text-slate-400 hover:text-inherit'
              }`}
              title="System Appearance"
            >
              <Laptop className="w-3.5 h-3.5" />
              <span className="text-[10px]">Auto</span>
            </button>
            <button
              onClick={() => handleAppearanceToggle('light')}
              aria-label="Light Theme"
              className={`flex-1 py-1 px-1.5 rounded-lg flex items-center justify-center gap-1 transition ${
                currentAppearance === 'light' ? 'bg-white/20 dark:bg-white/15 text-inherit font-bold shadow-sm' : 'text-slate-400 hover:text-inherit'
              }`}
              title="Light Appearance"
            >
              <Sun className="w-3.5 h-3.5" />
              <span className="text-[10px]">Light</span>
            </button>
            <button
              onClick={() => handleAppearanceToggle('dark')}
              aria-label="Dark Theme"
              className={`flex-1 py-1 px-1.5 rounded-lg flex items-center justify-center gap-1 transition ${
                currentAppearance === 'dark' ? 'bg-white/20 dark:bg-white/15 text-inherit font-bold shadow-sm' : 'text-slate-400 hover:text-inherit'
              }`}
              title="Dark Appearance"
            >
              <Moon className="w-3.5 h-3.5" />
              <span className="text-[10px]">Dark</span>
            </button>
          </div>
        ) : (
          <button
            onClick={() => {
              const next = currentAppearance === 'dark' ? 'light' : currentAppearance === 'light' ? 'system' : 'dark';
              handleAppearanceToggle(next);
            }}
            aria-label="Toggle theme appearance"
            className="w-full py-2 flex items-center justify-center rounded-xl hover:bg-black/10 dark:hover:bg-white/10 text-slate-400 hover:text-inherit transition relative group"
            title={`Theme: ${currentAppearance}`}
          >
            {currentAppearance === 'dark' && <Moon className="w-4 h-4" />}
            {currentAppearance === 'light' && <Sun className="w-4 h-4" />}
            {currentAppearance === 'system' && <Laptop className="w-4 h-4" />}
            <span className="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-[11px] rounded-lg shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition whitespace-nowrap z-50 border border-white/10">
              Theme: {currentAppearance}
            </span>
          </button>
        )}

        {/* Account / Profile Quick Action */}
        {(!isCompact || isMobileDrawer) ? (
          <div 
            onClick={() => handleNavClick('settings')}
            className="flex items-center justify-between p-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer transition group"
          >
            <div className="flex items-center space-x-2.5 overflow-hidden">
              <img
                src={displayedAvatar}
                alt={displayedName}
                className="w-7 h-7 rounded-full object-cover border border-white/10 shrink-0"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = MOCK_USER.avatar;
                }}
              />
              <div className="overflow-hidden">
                <span className="text-xs font-semibold text-inherit truncate block leading-tight">
                  {displayedName}
                </span>
                <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-mono">
                  <ShieldCheck className="w-3 h-3 inline" />
                  {isAuthenticated ? 'Sovereign' : 'Guest'}
                </span>
              </div>
            </div>
            <Settings className="w-4 h-4 text-slate-400 group-hover:text-inherit transition shrink-0" />
          </div>
        ) : (
          <div 
            onClick={() => handleNavClick('settings')}
            className="flex justify-center p-1.5 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer transition relative group"
            title="Account Settings"
          >
            <img
              src={displayedAvatar}
              alt={displayedName}
              className="w-7 h-7 rounded-full object-cover border border-white/10"
              onError={(e) => {
                (e.target as HTMLImageElement).src = MOCK_USER.avatar;
              }}
            />
            <span className="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-[11px] rounded-lg shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition whitespace-nowrap z-50 border border-white/10">
              {displayedName}
            </span>
          </div>
        )}
      </div>
    </aside>
  );
};
