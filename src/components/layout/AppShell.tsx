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

// Feature views (HomeDashboardView is eagerly loaded for instant LCP)
import { HomeDashboardView } from '../../features/home/HomeDashboardView';

// Lazy-loaded secondary views for code splitting and sub-200kB initial bundle
const AIAssistantView = React.lazy(() => import('../../features/ai-assistant/AIAssistantView').then(m => ({ default: m.AIAssistantView })));
const UniversalSearchView = React.lazy(() => import('../../features/search/UniversalSearchView').then(m => ({ default: m.UniversalSearchView })));
const ChatModuleView = React.lazy(() => import('../../features/chat/ChatModuleView').then(m => ({ default: m.ChatModuleView })));
const SocialFeedView = React.lazy(() => import('../../features/social/SocialFeedView').then(m => ({ default: m.SocialFeedView })));
const VideoStreamView = React.lazy(() => import('../../features/video/VideoStreamView').then(m => ({ default: m.VideoStreamView })));
const FoodDiningView = React.lazy(() => import('../../features/food/FoodDiningView').then(m => ({ default: m.FoodDiningView })));
const ShoppingView = React.lazy(() => import('../../features/shopping/ShoppingView').then(m => ({ default: m.ShoppingView })));
const PaymentsView = React.lazy(() => import('../../features/payments/PaymentsView').then(m => ({ default: m.PaymentsView })));
const CloudDriveView = React.lazy(() => import('../../features/cloud/CloudDriveView').then(m => ({ default: m.CloudDriveView })));
const CustomizationStudioView = React.lazy(() => import('../../features/customization/CustomizationStudioView').then(m => ({ default: m.CustomizationStudioView })));
const NotificationsCenterView = React.lazy(() => import('../../features/notifications/NotificationsCenterView').then(m => ({ default: m.NotificationsCenterView })));
const SettingsAccountView = React.lazy(() => import('../../features/settings/SettingsAccountView').then(m => ({ default: m.SettingsAccountView })));

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
          <React.Suspense fallback={
            <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
              <div 
                className="w-8 h-8 border-3 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: `${preferences.accentColor || '#8b5cf6'} transparent transparent transparent` }}
              />
              <span className="text-xs text-slate-400 font-mono tracking-wider">Loading module...</span>
            </div>
          }>
            {renderActiveModule()}
          </React.Suspense>
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
