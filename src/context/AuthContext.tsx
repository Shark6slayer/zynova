import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient, type UserProfileResponse, type RegisterPayload, type LoginPayload, type UpdateProfilePayload } from '../services/apiClient';

interface AuthContextType {
  user: UserProfileResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAuthModalOpen: boolean;
  authModalMode: 'login' | 'register';
  openLoginModal: () => void;
  openRegisterModal: () => void;
  closeAuthModal: () => void;
  setAuthModalMode: (mode: 'login' | 'register') => void;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (payload: UpdateProfilePayload) => Promise<UserProfileResponse>;
  deleteAccount: (password: string) => Promise<void>;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');

  const refreshSession = useCallback(async () => {
    const token = apiClient.getToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const me = await apiClient.getMe();
      setUser(me);
    } catch {
      // If getMe fails, attempt token refresh
      const refreshed = await apiClient.refreshToken();
      if (refreshed) {
        try {
          const me = await apiClient.getMe();
          setUser(me);
        } catch {
          setUser(null);
          apiClient.clearTokens();
        }
      } else {
        setUser(null);
        apiClient.clearTokens();
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  // Helper to parse claims from JWT token safely without external library
  const parseTokenUser = (token: string): UserProfileResponse | null => {
    try {
      const parts = token.split('.');
      if (parts.length < 2) return null;
      const base64Url = parts[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      const parsed = JSON.parse(jsonPayload);
      if (parsed.sub && parsed.email) {
        return {
          id: parsed.sub,
          email: parsed.email,
          username: parsed.username || parsed.email.split('@')[0],
          full_name: parsed.full_name || parsed.name || (parsed.username || parsed.email.split('@')[0]),
          avatar_url: parsed.avatar_url || null,
          bio: parsed.bio || null,
          created_at: parsed.created_at || new Date().toISOString(),
          is_active: true,
        };
      }
    } catch {
      // Fallback if token cannot be parsed
    }
    return null;
  };

  const login = async (payload: LoginPayload) => {
    setIsLoading(true);
    const t0 = performance.now();
    try {
      const loginRes = await apiClient.login(payload);
      const tLogin = performance.now();

      // If user profile is included in login response or in JWT token, use it immediately
      let me = loginRes.user || parseTokenUser(loginRes.access_token);
      let tMe = tLogin;
      let didFetchProfile = false;

      if (me) {
        // Immediately set user and close modal so authenticated UI renders in single tick
        setUser(me);
        setIsAuthModalOpen(false);

        // Fetch full profile in background without blocking the UI
        apiClient.getMe()
          .then((fullProfile) => {
            setUser(fullProfile);
          })
          .catch(() => {
            // Non-fatal, existing token claims remain active
          });
      } else {
        // Fallback for legacy token formats
        me = await apiClient.getMe();
        tMe = performance.now();
        didFetchProfile = true;
        setUser(me);
        setIsAuthModalOpen(false);
      }

      if (typeof window !== 'undefined') {
        const loginDuration = Math.round(tLogin - t0);
        const meDuration = didFetchProfile ? Math.round(tMe - tLogin) : 0;
        const totalDuration = Math.round(tMe - t0);
        // Safe timing instrumentation: measures latency without exposing credentials or tokens
        console.info(`[AuthTiming] Login request: ${loginDuration}ms | Profile load: ${meDuration}ms | Total auth: ${totalDuration}ms`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: RegisterPayload) => {
    setIsLoading(true);
    const t0 = performance.now();
    try {
      await apiClient.register(payload);
      const tReg = performance.now();
      // Automatically log in after registration
      const loginRes = await apiClient.login({ email: payload.email, password: payload.password });
      const tLogin = performance.now();
      let me = loginRes.user || parseTokenUser(loginRes.access_token);
      let tMe = tLogin;
      let didFetchProfile = false;

      if (me) {
        setUser(me);
        setIsAuthModalOpen(false);
        apiClient.getMe()
          .then((fullProfile) => {
            setUser(fullProfile);
          })
          .catch(() => {});
      } else {
        me = await apiClient.getMe();
        tMe = performance.now();
        didFetchProfile = true;
        setUser(me);
        setIsAuthModalOpen(false);
      }

      if (typeof window !== 'undefined') {
        const regDuration = Math.round(tReg - t0);
        const loginDuration = Math.round(tLogin - tReg);
        const meDuration = didFetchProfile ? Math.round(tMe - tLogin) : 0;
        const totalDuration = Math.round(tMe - t0);
        console.info(`[AuthTiming] Register: ${regDuration}ms | Login: ${loginDuration}ms | Profile: ${meDuration}ms | Total: ${totalDuration}ms`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiClient.logout();
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  };

  const updateProfile = async (payload: UpdateProfilePayload): Promise<UserProfileResponse> => {
    const updated = await apiClient.updateProfile(payload);
    setUser(updated);
    return updated;
  };

  const deleteAccount = async (password: string) => {
    await apiClient.deleteAccount(password);
    setUser(null);
  };

  const openLoginModal = () => {
    setAuthModalMode('login');
    setIsAuthModalOpen(true);
  };

  const openRegisterModal = () => {
    setAuthModalMode('register');
    setIsAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setIsAuthModalOpen(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        isAuthModalOpen,
        authModalMode,
        openLoginModal,
        openRegisterModal,
        closeAuthModal,
        setAuthModalMode,
        login,
        register,
        logout,
        updateProfile,
        deleteAccount,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
