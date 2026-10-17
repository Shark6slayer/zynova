import React, { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, Shield, User, Bell, Lock, 
  Database, Globe, Eye, Smartphone, HelpCircle, Check, 
  LogOut, AlertTriangle, Loader2, Save, Trash2, KeyRound, Palette 
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { SUPPORTED_LOCALES_LIST, getLanguageMetadata } from '../../i18n';
import type { AppLanguage } from '../../types';

export const SettingsAccountView: React.FC = () => {
  const { preferences, updatePreferences } = useApp();
  const { user, isAuthenticated, logout, updateProfile, deleteAccount, openLoginModal } = useAuth();

  const [saveToast, setSaveToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('Preferences Saved');
  const [langSearchQuery, setLangSearchQuery] = useState('');

  const filteredLanguages = SUPPORTED_LOCALES_LIST.filter((l) => {
    const q = langSearchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      l.name.toLowerCase().includes(q) ||
      l.nativeName.toLowerCase().includes(q) ||
      l.code.toLowerCase().includes(q) ||
      l.script.toLowerCase().includes(q)
    );
  });

  // Profile Edit State
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [fullNameInput, setFullNameInput] = useState('');
  const [bioInput, setBioInput] = useState('');
  const [avatarUrlInput, setAvatarUrlInput] = useState('');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState('');

  // Account Deletion Dialog State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (user) {
      setFullNameInput(user.full_name || '');
      setBioInput(user.bio || '');
      setAvatarUrlInput(user.avatar_url || '');
    } else {
      setFullNameInput('');
      setBioInput('');
      setAvatarUrlInput('');
    }
  }, [user]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2500);
  };

  const handleToggleMemory = () => {
    updatePreferences({ aiMemoryEnabled: !preferences.aiMemoryEnabled });
    showToast('AI Memory Updated');
  };

  const handleToggleMotion = () => {
    updatePreferences({ reducedMotion: !preferences.reducedMotion });
    showToast('Display Motion Updated');
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError('');

    if (!fullNameInput.trim()) {
      setProfileError('Full name cannot be blank.');
      return;
    }

    if (!isAuthenticated) {
      showToast('Sign in required to save profile');
      setIsEditingProfile(false);
      return;
    }

    setProfileSaving(true);
    try {
      await updateProfile({
        full_name: fullNameInput.trim(),
        bio: bioInput.trim() || undefined,
        avatar_url: avatarUrlInput.trim() || undefined,
      });
      showToast('Profile Saved to Database');
      setIsEditingProfile(false);
    } catch (err: any) {
      setProfileError(err.message || 'Failed to update profile.');
    } finally {
      setProfileSaving(false);
    }
  };

  const handleDeleteAccountConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeleteError('');

    if (!deletePassword) {
      setDeleteError('Password is required to confirm account deletion.');
      return;
    }

    setIsDeleting(true);
    try {
      await deleteAccount(deletePassword);
      setIsDeleteModalOpen(false);
      setDeletePassword('');
      showToast('Account Deleted Successfully');
    } catch (err: any) {
      setDeleteError(err.message || 'Incorrect password or deletion error.');
    } finally {
      setIsDeleting(false);
    }
  };

  const displayedName = user?.full_name || (user?.username ? `@${user.username}` : 'Guest User');
  const displayedHandle = user ? `@${user.username}` : '@guest';
  const displayedAvatar = user?.avatar_url || '';
  const displayedEmail = user?.email || 'Not signed in';

  return (
    <div className="space-y-6 max-w-4xl mx-auto w-full pb-10">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-violet-400 text-xs font-semibold uppercase tracking-wider">
            <SettingsIcon className="w-4 h-4" />
            <span>Account & System Control</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Settings & Privacy Hub</h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage your personal profile, privacy boundaries, AI memory retention, and connected devices.
          </p>
        </div>

        {saveToast && (
          <div className="p-2.5 px-3 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-1.5 animate-in fade-in">
            <Check className="w-4 h-4" />
            <span>{toastMessage}</span>
          </div>
        )}
      </div>

      {/* User Profile Card */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/10 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            {displayedAvatar ? (
              <img 
                src={displayedAvatar} 
                alt={displayedName} 
                className="w-14 h-14 rounded-full object-cover border-2 border-violet-500/40"
              />
            ) : (
              <div className="w-14 h-14 rounded-full bg-violet-600/30 border-2 border-violet-500/40 flex items-center justify-center text-lg font-bold text-violet-200">
                {displayedName.charAt(0).toUpperCase()}
              </div>
            )}
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-1.5">
                {displayedName}
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold ${
                  isAuthenticated 
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
                    : 'bg-slate-500/20 text-slate-400 border border-slate-500/30'
                }`}>
                  {isAuthenticated ? 'VERIFIED SOVEREIGN ID' : 'GUEST SESSION'}
                </span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">{displayedHandle} • {displayedEmail}</p>
              {user?.bio && (
                <p className="text-xs text-slate-300 mt-1.5 italic max-w-lg">"{user.bio}"</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!isAuthenticated ? (
              <button
                onClick={openLoginModal}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-xs font-semibold text-white shadow-lg shadow-violet-500/20 transition"
              >
                Sign In / Register
              </button>
            ) : (
              <>
                <button
                  onClick={() => setIsEditingProfile(!isEditingProfile)}
                  className="px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-200 border border-white/10 transition"
                >
                  {isEditingProfile ? 'Cancel' : 'Edit Profile'}
                </button>
                <button
                  onClick={logout}
                  className="px-3.5 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-xs text-rose-300 border border-rose-500/30 flex items-center gap-1.5 transition"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Logout</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Profile Edit Form */}
        {isEditingProfile && (
          <form onSubmit={handleSaveProfile} className="mt-4 pt-4 border-t border-white/10 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-violet-400">Edit Profile Information</h4>

            {profileError && (
              <div className="p-2.5 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs">
                {profileError}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Full Name</label>
                <input
                  type="text"
                  value={fullNameInput}
                  onChange={(e) => setFullNameInput(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-violet-500"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Avatar Image URL (Optional)</label>
                <input
                  type="url"
                  value={avatarUrlInput}
                  onChange={(e) => setAvatarUrlInput(e.target.value)}
                  placeholder="https://images.unsplash.com/..."
                  className="w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-violet-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">Bio / Status</label>
              <textarea
                value={bioInput}
                onChange={(e) => setBioInput(e.target.value)}
                placeholder="Tell the community about your interests..."
                rows={2}
                maxLength={280}
                className="w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-violet-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsEditingProfile(false)}
                className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-300 border border-white/10"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={profileSaving}
                className="px-4 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white flex items-center gap-1.5 transition disabled:opacity-50"
              >
                {profileSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Save Changes</span>
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Appearance & Theme Engine */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/10 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Palette className="w-4 h-4 text-violet-400" /> Appearance & Theme Mode
        </h3>

        <div className="grid grid-cols-3 gap-3">
          {[
            { id: 'system', label: 'System (Auto)' },
            { id: 'light', label: 'Light Mode' },
            { id: 'dark', label: 'Dark Mode' },
          ].map((item) => {
            const isSelected = (preferences.appearanceMode || 'system') === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  updatePreferences({ appearanceMode: item.id as any });
                  showToast(`Switched to ${item.label}`);
                }}
                className={`py-2 px-3 rounded-xl border text-xs font-semibold transition ${
                  isSelected
                    ? 'border-violet-500 bg-violet-600/30 text-white shadow-md'
                    : 'border-white/5 bg-slate-800/40 text-slate-300 hover:bg-slate-800'
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* India's 22-Language Experience (Eighth Schedule of the Constitution of India) */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/10 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Globe className="w-4 h-4 text-indigo-400" /> India's 22-Language Sovereign Experience
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Select any of the 22 Eighth Schedule languages. Instant preview with full script and direction support.
            </p>
          </div>
          <div className="text-[11px] font-mono px-2.5 py-1 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 w-fit">
            ACTIVE: {getLanguageMetadata(preferences.language).nativeName} ({getLanguageMetadata(preferences.language).name})
          </div>
        </div>

        {/* Search input for languages */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search language by English name, native script, or code..."
            value={langSearchQuery}
            onChange={(e) => setLangSearchQuery(e.target.value)}
            className="w-full px-3 py-2 rounded-xl bg-black/40 border border-white/10 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        {/* 22 Languages Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5 max-h-72 overflow-y-auto p-1 pr-2">
          {filteredLanguages.map((lang) => {
            const isSelected = preferences.language === lang.code;
            return (
              <button
                key={lang.code}
                onClick={() => {
                  updatePreferences({ language: lang.code as AppLanguage });
                  showToast(`Language switched to ${lang.nativeName} (${lang.name})`);
                }}
                className={`p-3 rounded-xl border text-left transition relative flex flex-col justify-between ${
                  isSelected
                    ? 'border-indigo-500 bg-indigo-600/25 text-white ring-1 ring-indigo-500/50 shadow-md'
                    : 'border-white/5 bg-slate-800/40 text-slate-300 hover:bg-slate-800 hover:border-white/15'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold tracking-wide">{lang.nativeName}</span>
                    {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{lang.name}</div>
                </div>

                <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-white/5 text-[9px]">
                  <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-400 font-mono">
                    {lang.script}
                  </span>
                  {lang.direction === 'rtl' && (
                    <span className="px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
                      RTL
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Privacy & Sovereign AI Memory Controls */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/10 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-400" /> Sovereign Privacy & Data Protection
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-800/40 border border-white/5">
            <div>
              <h5 className="text-xs font-semibold text-slate-200">Sovereign AI Memory & Context Cache</h5>
              <p className="text-[11px] text-slate-400">Allow SUPER_AI models to remember dietary, travel, and coding habits locally.</p>
            </div>
            <button
              onClick={handleToggleMemory}
              className={`w-11 h-6 rounded-full transition-colors relative p-0.5 ${
                preferences.aiMemoryEnabled ? 'bg-violet-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`block w-5 h-5 rounded-full bg-white transition-transform ${
                  preferences.aiMemoryEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-800/40 border border-white/5">
            <div>
              <h5 className="text-xs font-semibold text-slate-200">Reduced Motion & Animation Throttle</h5>
              <p className="text-[11px] text-slate-400">Minimize ambient blur effects and layout transitions for battery saving.</p>
            </div>
            <button
              onClick={handleToggleMotion}
              className={`w-11 h-6 rounded-full transition-colors relative p-0.5 ${
                preferences.reducedMotion ? 'bg-violet-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`block w-5 h-5 rounded-full bg-white transition-transform ${
                  preferences.reducedMotion ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-800/40 border border-white/5">
            <div>
              <h5 className="text-xs font-semibold text-slate-200">Digital Personal Data Protection (DPDP) Audit</h5>
              <p className="text-[11px] text-slate-400">All data transactions comply with Indian sovereign digital sovereignty standards.</p>
            </div>
            <span className="text-[10px] px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold">
              COMPLIANT
            </span>
          </div>
        </div>
      </div>

      {/* Account Lifecycle & Danger Zone */}
      {isAuthenticated && (
        <div className="p-6 rounded-2xl bg-rose-950/20 border border-rose-500/20 space-y-4">
          <div className="flex items-center gap-2 text-rose-400 text-sm font-bold">
            <AlertTriangle className="w-4 h-4" />
            <span>Danger Zone & Account Lifecycle</span>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-black/40 border border-rose-500/20">
            <div>
              <h5 className="text-xs font-bold text-white">Delete Sovereign Account</h5>
              <p className="text-[11px] text-slate-400 max-w-md mt-0.5">
                Permanently purge your account, preferences, conversations, and notifications in accordance with DPDP right to be forgotten. This cannot be undone.
              </p>
            </div>
            <button
              onClick={() => setIsDeleteModalOpen(true)}
              className="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-xs font-bold text-white flex items-center justify-center gap-1.5 transition shrink-0"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Account</span>
            </button>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md bg-slate-900 border border-rose-500/30 rounded-3xl p-6 shadow-2xl space-y-4 text-white">
            <div className="flex items-center space-x-2 text-rose-400 text-xs font-bold uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <span>Confirm Account Deletion</span>
            </div>
            <h3 className="text-xl font-bold">Irreversible Action</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Please enter your password to confirm deletion of your account. All your preferences, conversations, active tokens, and personal records will be permanently removed.
            </p>

            {deleteError && (
              <div className="p-3 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs">
                {deleteError}
              </div>
            )}

            <form onSubmit={handleDeleteAccountConfirm} className="space-y-4">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Enter Password</label>
                <div className="relative">
                  <KeyRound className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                  <input
                    type="password"
                    required
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-rose-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsDeleteModalOpen(false);
                    setDeletePassword('');
                    setDeleteError('');
                  }}
                  className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-300 border border-white/10"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isDeleting}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-xs font-bold text-white flex items-center gap-1.5 transition disabled:opacity-50"
                >
                  {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  <span>Permanently Delete</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
