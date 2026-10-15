import React, { useState } from 'react';
import { 
  X, Lock, Mail, User, Shield, AlertCircle, 
  CheckCircle2, ArrowRight, Loader2, Eye, EyeOff 
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useApp } from '../../context/AppContext';

export const AuthModal: React.FC = () => {
  const { 
    isAuthModalOpen, 
    closeAuthModal, 
    authModalMode, 
    setAuthModalMode, 
    login, 
    register 
  } = useAuth();
  const { syncPreferencesWithServer } = useApp();

  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isAuthModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (!email.trim() || !password) {
      setErrorMsg('Please provide your email and password.');
      return;
    }

    if (authModalMode === 'register') {
      if (!username.trim() || !fullName.trim()) {
        setErrorMsg('Please fill in your username and full name.');
        return;
      }
      if (password.length < 8) {
        setErrorMsg('Password must be at least 8 characters long.');
        return;
      }
      if (!/\d/.test(password)) {
        setErrorMsg('Password must contain at least one digit.');
        return;
      }
      if (!/[a-zA-Z]/.test(password)) {
        setErrorMsg('Password must contain at least one letter.');
        return;
      }
    }

    setIsSubmitting(true);
    try {
      if (authModalMode === 'login') {
        await login({ email: email.trim(), password });
        setSuccessMsg('Logged in successfully!');
        await syncPreferencesWithServer();
      } else {
        await register({
          email: email.trim(),
          username: username.trim().toLowerCase(),
          full_name: fullName.trim(),
          password,
        });
        setSuccessMsg('Account created and logged in!');
        await syncPreferencesWithServer();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSwitchMode = (mode: 'login' | 'register') => {
    setErrorMsg('');
    setSuccessMsg('');
    setAuthModalMode(mode);
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200"
      onClick={closeAuthModal}
    >
      <div 
        className="relative w-full max-w-md bg-slate-900/90 border border-white/15 rounded-3xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl text-white"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={closeAuthModal}
          className="absolute top-5 right-5 p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center space-x-2 text-violet-400 text-xs font-semibold uppercase tracking-wider mb-2">
          <Shield className="w-4 h-4 text-violet-400" />
          <span>Sovereign Identity</span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          {authModalMode === 'login' ? 'Welcome to SUPER_AI' : 'Create Sovereign Account'}
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          {authModalMode === 'login'
            ? 'Access your unified 15-module super ecosystem, encrypted drive & preferences.'
            : 'Register to unlock persistent preferences, cross-device sync & DPDP compliant data protection.'}
        </p>

        {/* Alert Messages */}
        {errorMsg && (
          <div className="mt-4 p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mt-4 p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-5 space-y-3.5">
          {authModalMode === 'register' && (
            <>
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Ananya Sharma"
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-black/40 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-violet-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Username
                </label>
                <div className="relative">
                  <span className="text-slate-400 text-xs absolute left-3 top-2.5 font-mono">@</span>
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="ananya_ai"
                    className="w-full pl-8 pr-3 py-2 rounded-xl bg-black/40 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-violet-500 transition"
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full pl-9 pr-3 py-2 rounded-xl bg-black/40 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-violet-500 transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-9 pr-10 py-2 rounded-xl bg-black/40 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-violet-500 transition"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-white"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {authModalMode === 'register' && (
              <p className="text-[10px] text-slate-500 mt-1">
                Min. 8 characters, with letters and numbers.
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 font-semibold text-xs text-white shadow-lg shadow-violet-500/25 flex items-center justify-center space-x-2 transition disabled:opacity-50"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span>{authModalMode === 'login' ? 'Sign In to SUPER_AI' : 'Create Account'}</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Mode Switcher */}
        <div className="mt-6 pt-4 border-t border-white/10 text-center">
          {authModalMode === 'login' ? (
            <p className="text-xs text-slate-400">
              Don't have an account yet?{' '}
              <button
                type="button"
                onClick={() => handleSwitchMode('register')}
                className="text-violet-400 font-semibold hover:underline"
              >
                Register now
              </button>
            </p>
          ) : (
            <p className="text-xs text-slate-400">
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => handleSwitchMode('login')}
                className="text-violet-400 font-semibold hover:underline"
              >
                Sign In
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
