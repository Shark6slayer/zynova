import React, { useState, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { CommandPalette } from '../overlays/CommandPalette';
import { OnboardingModal } from '../overlays/OnboardingModal';
import { 
  Home, Search, MessageSquare, 
  ShoppingBag, Utensils, CreditCard, Menu 
} from 'lucide-react';
import type { NavModuleId } from '../../types';
import { t } from '../../i18n';

// Feature views (lazy evaluation & active modules)
import { HomeDashboardView } from '../../features/home/HomeDashboardView';
import { AIAssistantView } from '../../features/ai-assistant/AIAssistantView';
import { UniversalSearchView } from '../../features/search/UniversalSearchView';
import { ChatModuleView } from '../../features/chat/ChatModuleView';
import { SocialFeedView } from '../../features/social/SocialFeedView';
import { VideoStreamView } from '../../features/video/VideoStreamView';
import { FoodDiningView } from '../../features/food/FoodDiningView';
import { ShoppingView } from '../../features/shopping/ShoppingView';
import { PaymentsView } from '../../features/payments/PaymentsView';
import { CloudDriveView } from '../../features/cloud/CloudDriveView';
import { CustomizationStudioView } from '../../features/customization/CustomizationStudioView';
import { NotificationsCenterView } from '../../features/notifications/NotificationsCenterView';
import { SettingsAccountView } from '../../features/settings/SettingsAccountView';

export const AppShell: React.FC = () => {
  const { activeModule, setActiveModule, activeTheme, preferences, isMobileNavOpen, setIsMobileNavOpen } = useApp();
  const [showOnboarding, setShowOnboarding] = useState(!preferences.onboardingCompleted);

  // Prevent background scrolling while the mobile drawer is open
  useEffect(() => {
    if (isMobileNavOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileNavOpen]);

  // Handle hardware Android back button and Escape key to close mobile drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isMobileNavOpen) {
        setIsMobileNavOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMobileNavOpen, setIsMobileNavOpen]);

  const renderActiveModule = () => {
    switch (activeModule) {
      case 'home':
        return <HomeDashboardView />;
      case 'ai-assistant':
        return <AIAssistantView />;
      case 'search':
        return <UniversalSearchView />;
      case 'chat':
        return <ChatModuleView />;
      case 'social':
        return <SocialFeedView />;
      case 'video':
        return <VideoStreamView />;
      case 'shopping':
        return <ShoppingView />;
      case 'food':
        return <FoodDiningView />;
      case 'payments':
        return <PaymentsView />;
      case 'cloud':
        return <CloudDriveView />;
      case 'customization':
        return <CustomizationStudioView />;
      case 'notifications':
        return <NotificationsCenterView />;
      case 'settings':
        return <SettingsAccountView />;
      default:
        return <HomeDashboardView />;
    }
  };

  const mobileNavDestinations: Array<{ id: NavModuleId; labelKey: string; fallback: string; icon: any }> = [
    { id: 'home', labelKey: 'nav.home', fallback: 'Home', icon: Home },
    { id: 'search', labelKey: 'nav.search', fallback: 'Search', icon: Search },
    { id: 'chat', labelKey: 'nav.chat', fallback: 'Chat', icon: MessageSquare },
    { id: 'shopping', labelKey: 'nav.shopping', fallback: 'Zaviro', icon: ShoppingBag },
    { id: 'food', labelKey: 'nav.food', fallback: 'Food', icon: Utensils },
    { id: 'payments', labelKey: 'nav.payments', fallback: 'Pay', icon: CreditCard },
  ];

  return (
    <div className={`flex h-screen w-screen overflow-hidden ${activeTheme.bgClass} ${activeTheme.textClass} font-sans`}>
      {/* Desktop Sidebar (ChatGPT-style responsive collapsible) */}
      <div className="hidden md:flex h-full shrink-0">
        <Sidebar />
      </div>

      {/* Mobile Drawer Sidebar with animated backdrop & touch dismiss */}
      {isMobileNavOpen && (
        <div 
          className="fixed inset-0 z-50 md:hidden flex"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation Menu"
        >
          <div 
            className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity animate-in fade-in duration-200" 
            onClick={() => setIsMobileNavOpen(false)} 
            aria-hidden="true"
          />
          <div className="relative z-50 h-full max-w-[80vw] animate-in slide-in-from-left duration-300">
            <Sidebar isMobileDrawer={true} onCloseMobile={() => setIsMobileNavOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
        <TopBar />

        {/* Ambient Subtle Glow Gradient */}
        <div 
          className="absolute top-0 right-0 w-96 h-96 rounded-full blur-3xl pointer-events-none opacity-20"
          style={{ background: activeTheme.accentGlow }}
        />

        {/* Scrollable View Area (with bottom padding on mobile for touch navigation) */}
        <main 
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto p-3.5 sm:p-5 md:p-6 pb-20 md:pb-6 relative z-10 focus:outline-none"
        >
          {renderActiveModule()}
        </main>

        {/* Mobile Sticky Bottom Navigation Bar */}
        <nav 
          aria-label="Mobile Bottom Navigation"
          className={`md:hidden fixed bottom-0 inset-x-0 h-16 pb-safe border-t ${activeTheme.borderClass} ${activeTheme.surfaceClass} flex items-center justify-around px-2 z-30 shadow-2xl`}
        >
          {mobileNavDestinations.map((m) => {
            const Icon = m.icon;
            const isActive = activeModule === m.id;
            const localizedLabel = t(m.labelKey, preferences.language) || m.fallback;
            return (
              <button
                key={m.id}
                onClick={() => setActiveModule(m.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`flex flex-col items-center justify-center p-1.5 rounded-xl transition ${
                  isActive ? 'font-bold' : 'text-slate-400 hover:text-inherit'
                }`}
                style={isActive ? { color: preferences.accentColor || '#8b5cf6' } : undefined}
              >
                <Icon 
                  className={`w-5 h-5 transition-transform ${isActive ? 'scale-110' : ''}`} 
                  style={isActive ? { color: preferences.accentColor || '#8b5cf6' } : undefined}
                />
                <span className="text-[10px] tracking-tight mt-0.5">{localizedLabel}</span>
              </button>
            );
          })}
          <button
            onClick={() => setIsMobileNavOpen(true)}
            aria-label="Open full menu"
            className="flex flex-col items-center justify-center p-1.5 rounded-xl text-slate-400 hover:text-inherit transition"
          >
            <Menu className="w-5 h-5" />
            <span className="text-[10px] tracking-tight mt-0.5">{t('nav.menu', preferences.language) || 'Menu'}</span>
          </button>
        </nav>
      </div>

      {/* Command Palette (Ctrl+K) */}
      <CommandPalette />

      {/* First-run Onboarding Modal */}
      {showOnboarding && <OnboardingModal onClose={() => setShowOnboarding(false)} />}
    </div>
  );
};
