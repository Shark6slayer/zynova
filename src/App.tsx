import React from 'react';
import { AppProvider } from './context/AppContext';
import { AuthProvider } from './context/AuthContext';
import { AppShell } from './components/layout/AppShell';
import { AuthModal } from './components/overlays/AuthModal';

export function App() {
  return (
    <AuthProvider>
      <AppProvider>
        <AppShell />
        <AuthModal />
      </AppProvider>
    </AuthProvider>
  );
}

export default App;
