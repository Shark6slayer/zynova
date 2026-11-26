import React, { useEffect, useState } from 'react';
import { AppProvider } from './context/AppContext';
import { AuthProvider } from './context/AuthContext';
import { OfflineSyncProvider } from './context/OfflineSyncContext';
import { AppShell } from './components/layout/AppShell';
import { AuthModal } from './components/overlays/AuthModal';

const PrivacyPolicyView = React.lazy(() =>
  import('./features/public/PrivacyPolicyView').then((m) => ({ default: m.PrivacyPolicyView }))
);
const TermsOfServiceView = React.lazy(() =>
  import('./features/public/TermsOfServiceView').then((m) => ({ default: m.TermsOfServiceView }))
);
const ChildSafetyStandardsView = React.lazy(() =>
  import('./features/public/ChildSafetyStandardsView').then((m) => ({ default: m.ChildSafetyStandardsView }))
);
const CommunityGuidelinesView = React.lazy(() =>
  import('./features/public/CommunityGuidelinesView').then((m) => ({ default: m.CommunityGuidelinesView }))
);
const ContentModerationView = React.lazy(() =>
  import('./features/public/ContentModerationView').then((m) => ({ default: m.ContentModerationView }))
);
const DataRightsView = React.lazy(() =>
  import('./features/public/DataRightsView').then((m) => ({ default: m.DataRightsView }))
);
const AccountDeletionView = React.lazy(() =>
  import('./features/public/AccountDeletionView').then((m) => ({ default: m.AccountDeletionView }))
);
const ContactSupportView = React.lazy(() =>
  import('./features/public/ContactSupportView').then((m) => ({ default: m.ContactSupportView }))
);
const SafetyCenterView = React.lazy(() =>
  import('./features/public/SafetyCenterView').then((m) => ({ default: m.SafetyCenterView }))
);
const NotFoundView = React.lazy(() =>
  import('./features/public/NotFoundView').then((m) => ({ default: m.NotFoundView }))
);

const PUBLIC_ROUTE_MAP: Record<string, React.LazyExoticComponent<React.FC>> = {
  '/privacy-policy': PrivacyPolicyView,
  '/privacy': PrivacyPolicyView,
  '/terms': TermsOfServiceView,
  '/terms-of-service': TermsOfServiceView,
  '/child-safety': ChildSafetyStandardsView,
  '/child-safety-standards': ChildSafetyStandardsView,
  '/community-guidelines': CommunityGuidelinesView,
  '/content-moderation': ContentModerationView,
  '/data-rights': DataRightsView,
  '/delete-account': AccountDeletionView,
  '/data-deletion': AccountDeletionView,
  '/contact': ContactSupportView,
  '/safety': SafetyCenterView,
};

const APP_SHELL_ROUTES = new Set(['/', '/index.html', '/settings/connections']);

function normalizePathname(raw: string): string {
  const trimmed = raw.replace(/\/+$/, '').toLowerCase();
  return trimmed === '' ? '/' : trimmed;
}

const PublicFallback = () => (
  <div className="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center space-y-3">
    <div className="w-8 h-8 border-3 border-purple-500 border-t-transparent rounded-full animate-spin" />
    <span className="text-xs text-slate-400 font-mono tracking-wider">Loading page...</span>
  </div>
);

export function App() {
  const [pathname, setPathname] = useState<string>(() =>
    typeof window !== 'undefined' ? normalizePathname(window.location.pathname) : '/'
  );

  useEffect(() => {
    const onPopState = () => {
      setPathname(normalizePathname(window.location.pathname));
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const PublicComponent = PUBLIC_ROUTE_MAP[pathname];
  if (PublicComponent) {
    return (
      <React.Suspense fallback={<PublicFallback />}>
        <PublicComponent />
      </React.Suspense>
    );
  }

  if (!APP_SHELL_ROUTES.has(pathname)) {
    return (
      <React.Suspense fallback={<PublicFallback />}>
        <NotFoundView />
      </React.Suspense>
    );
  }

  return (
    <AuthProvider>
      <OfflineSyncProvider>
        <AppProvider>
          <AppShell />
          <AuthModal />
        </AppProvider>
      </OfflineSyncProvider>
    </AuthProvider>
  );
}

export default App;
