import React from 'react';
import { 
  Search, Bell, Sparkles, Menu, Palette, LogIn 
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { t } from '../../i18n';
import { MOCK_USER } from '../../mocks/demoData';

export const TopBar: React.FC = () => {
  const { 
    preferences, 
    activeTheme, 
    setActiveModule, 
    setIsCommandPaletteOpen, 
    setIsMobileNavOpen,
    unreadNotificationsCount 
  } = useApp();
  const { user, isAuthenticated, openLoginModal } = useAuth();

  const displayedAvatar = user?.avatar_url || MOCK_USER.avatar;
  const displayedName = user?.full_name || MOCK_USER.name;

  return (
    <header className={`h-14 border-b ${activeTheme.borderClass} ${activeTheme.surfaceClass} flex items-center justify-between px-4 z-20 shrink-0`}>
      {/* Mobile Menu & Global Search Trigger */}
      <div className="flex items-center space-x-3 flex-1 max-w-xl">
        <button
          onClick={() => setIsMobileNavOpen(true)}
          className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Global Search Bar (opens command palette or search module) */}
        <div
          onClick={() => setIsCommandPaletteOpen(true)}
          className="w-full flex items-center space-x-2.5 px-3 py-1.5 rounded-xl bg-black/30 border border-white/10 hover:border-violet-500/40 cursor-pointer transition text-xs text-slate-400"
        >
          <Search className="w-4 h-4 text-violet-400 shrink-0" />
          <span className="truncate flex-1">
            {t('common.search_placeholder', preferences.language)}
          </span>
          <div className="hidden sm:flex items-center space-x-1 px-1.5 py-0.5 rounded bg-white/10 text-[10px] text-slate-300 font-mono">
            <span>Ctrl</span>
            <span>K</span>
          </div>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-2 pl-4">
        {/* Theme Studio Quick Action */}
        <button
          onClick={() => setActiveModule('customization')}
          className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition"
          title="Open Customization Studio"
        >
          <Palette className="w-4 h-4" />
        </button>

        {/* Notifications Icon with Counter */}
        <button
          onClick={() => setActiveModule('notifications')}
          className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition relative"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
          {unreadNotificationsCount > 0 && (
            <span className="w-2 h-2 rounded-full bg-violet-500 absolute top-1.5 right-1.5 ring-2 ring-slate-900" />
          )}
        </button>

        {/* User Profile or Sign In */}
        {isAuthenticated ? (
          <div
            onClick={() => setActiveModule('settings')}
            className="flex items-center space-x-2 pl-2 cursor-pointer group"
            title="Account Settings"
          >
            <img
              src={displayedAvatar}
              alt={displayedName}
              className="w-8 h-8 rounded-full object-cover border border-violet-500/30 group-hover:border-violet-400 transition"
              onError={(e) => {
                (e.target as HTMLImageElement).src = MOCK_USER.avatar;
              }}
            />
            <div className="hidden lg:block text-left">
              <span className="text-xs font-semibold text-slate-200 block leading-tight">{displayedName}</span>
              <span className="text-[10px] text-emerald-400 block font-mono font-medium">SOVEREIGN</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center space-x-2 pl-1">
            <button
              onClick={openLoginModal}
              className="px-3 py-1.5 rounded-xl bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 border border-violet-500/40 text-xs font-semibold flex items-center space-x-1.5 transition"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign In</span>
            </button>
            <div
              onClick={() => setActiveModule('settings')}
              className="cursor-pointer group"
              title="Guest Settings"
            >
              <img
                src={MOCK_USER.avatar}
                alt="Guest"
                className="w-8 h-8 rounded-full object-cover border border-white/20 group-hover:border-violet-400 transition opacity-70 group-hover:opacity-100"
              />
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
