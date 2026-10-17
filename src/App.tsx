import React from 'react';
import { AppProvider } from './context/AppContext';
import { AuthProvider } from './context/AuthContext';
import { OfflineSyncProvider } from './context/OfflineSyncContext';
import { AppShell } from './components/layout/AppShell';
import { AuthModal } from './components/overlays/AuthModal';

export function App() {
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
