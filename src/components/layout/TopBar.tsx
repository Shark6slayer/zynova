import React from 'react';
import { 
  Search, Bell, Sparkles, Menu, Palette, LogIn, User 
} from 'lucide-react';
import { ConnectivityBadge } from '../common/ConnectivityBadge';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { t } from '../../i18n';

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

  const displayedAvatar = user?.avatar_url || '';
  const displayedName = user?.full_name || user?.username || 'Guest';

  return (
    <header className={`pt-safe border-b ${activeTheme.borderClass} ${activeTheme.surfaceClass} z-20 shrink-0 sticky top-0`}>
      <div className="h-14 flex items-center justify-between px-2.5 sm:px-4 gap-2">
        {/* Mobile Menu & Global Search Trigger */}
        <div className="flex items-center gap-2 flex-1 min-w-0 max-w-xl">
          <button
            onClick={() => setIsMobileNavOpen(true)}
            aria-label="Open navigation menu"
            className="md:hidden min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-white/5 active:bg-white/10 transition shrink-0"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* Global Search Bar (opens command palette or search module) */}
          <div
            onClick={() => setIsCommandPaletteOpen(true)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setIsCommandPaletteOpen(true);
              }
            }}
            aria-label="Search Zynova"
            className="flex-1 min-w-0 h-10 flex items-center gap-2 px-3 rounded-xl bg-black/30 border border-white/10 hover:border-violet-500/40 active:border-violet-500/60 cursor-pointer transition text-xs text-slate-400"
          >
            <Search className="w-4 h-4 text-violet-400 shrink-0" />
            <span className="truncate flex-1 text-left select-none">
              <span className="hidden sm:inline">
                {t('common.search_placeholder', preferences.language)}
              </span>
              <span className="sm:hidden">
                {t('common.search_placeholder_short', preferences.language) || 'Search Zynova...'}
              </span>
            </span>
            <div className="hidden sm:flex items-center space-x-1 px-1.5 py-0.5 rounded bg-white/10 text-[10px] text-slate-300 font-mono shrink-0">
              <span>Ctrl</span>
              <span>K</span>
            </div>
          </div>
        </div>

        {/* Right Controls */}
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          {/* Connectivity Status Indicator */}
          <ConnectivityBadge />

          {/* Theme Studio Quick Action */}
          <button
            onClick={() => setActiveModule('customization')}
            aria-label="Open Customization Studio"
            className="min-w-[40px] min-h-[40px] flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-white/5 active:bg-white/10 transition"
            title="Open Customization Studio"
          >
            <Palette className="w-4 h-4" />
          </button>

          {/* Notifications Icon with Counter */}
          <button
            onClick={() => setActiveModule('notifications')}
            aria-label="Notifications"
            className="min-w-[40px] min-h-[40px] flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-white/5 active:bg-white/10 transition relative"
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadNotificationsCount > 0 && (
              <span className="w-2 h-2 rounded-full bg-violet-500 absolute top-2 right-2 ring-2 ring-slate-900" />
            )}
          </button>

          {/* User Profile or Sign In */}
          {isAuthenticated ? (
            <div
              onClick={() => setActiveModule('settings')}
              className="flex items-center space-x-2 pl-1 cursor-pointer group min-h-[44px]"
              title="Account Settings"
            >
              {displayedAvatar ? (
                <img
                  src={displayedAvatar}
                  alt={displayedName}
                  className="w-8 h-8 rounded-full object-cover border border-violet-500/30 group-hover:border-violet-400 transition"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-violet-600/30 border border-violet-500/40 flex items-center justify-center text-xs font-bold text-violet-200">
                  {displayedName.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="hidden lg:block text-left">
                <span className="text-xs font-semibold text-slate-200 block leading-tight">{displayedName}</span>
                <span className="text-[10px] text-emerald-400 block font-mono font-medium">SOVEREIGN</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center space-x-1 sm:space-x-2">
              <button
                onClick={openLoginModal}
                className="min-h-[36px] px-2.5 sm:px-3 py-1.5 rounded-xl bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 border border-violet-500/40 text-xs font-semibold flex items-center space-x-1.5 transition"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Sign In</span>
              </button>
              <div
                onClick={() => setActiveModule('settings')}
                className="cursor-pointer group min-w-[40px] min-h-[40px] flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition"
                title="Guest Settings"
              >
                <User className="w-5 h-5 text-slate-400 group-hover:text-violet-300" />
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
