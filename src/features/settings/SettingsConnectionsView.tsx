import React, { useState, useEffect } from 'react';
import { 
  Share2, Check, AlertTriangle, AlertCircle, 
  Loader2, RefreshCw, Unlink, Download, ExternalLink, 
  ShieldCheck, ArrowLeft, Info, CheckCircle2 
} from 'lucide-react';
import { InstagramIcon } from '../../components/icons/InstagramIcon';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../services/apiClient';
import { InstagramImportModal } from '../../components/social/InstagramImportModal';

export const SettingsConnectionsView: React.FC = () => {
  const { setActiveModule, activeTheme } = useApp();
  const { user, isAuthenticated, openLoginModal } = useAuth();

  const [igStatus, setIgStatus] = useState<{
    connected: boolean;
    username: string | null;
    status: 'active' | 'needs_reconnect' | 'not_connected';
    last_synced_at: string | null;
    media_count: number | null;
  } | null>(null);

  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Toast State
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showToast = (type: 'success' | 'error', message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  };

  const parseErrorMessage = (code: string | null): string => {
    if (!code) return 'Instagram authorization was unsuccessful.';
    switch (code) {
      case 'access_denied':
        return 'Access was denied. Please approve the required permissions in Meta login.';
      case 'user_denied':
        return 'You cancelled the Instagram authorization flow.';
      case 'invalid_state':
      case 'state_invalid_or_expired':
        return 'Authorization session expired or was invalid. Please try connecting again.';
      case 'no_instagram_business_account_found':
        return 'No Instagram Business or Creator account found on your Facebook Pages.';
      case 'redirect_mismatch':
        return 'Meta OAuth redirect URI mismatch. Please verify INSTAGRAM_REDIRECT_URI in backend environment and Meta App settings.';
      case 'code_used_or_expired':
        return 'The authorization code has expired or was already used. Please click Connect Instagram to start a fresh authorization.';
      case 'invalid_secret':
        return 'Invalid Meta App Secret configured on the backend. Please verify META_APP_SECRET in Render.';
      case 'token_exchange_failed':
        return 'Failed to exchange tokens with Meta Graph API. Please try again.';
      default:
        return `Authorization failed (${code}).`;
    }
  };

  useEffect(() => {
    // Process OAuth redirection queries (?ig=success or ?ig=error&error=<code>)
    const params = new URLSearchParams(window.location.search);
    const igParam = params.get('ig');
    const errCode = params.get('error');

    if (igParam === 'success') {
      if (!isAuthenticated) {
        // If not logged in yet, prompt sign in and retain context
        openLoginModal();
      } else {
        showToast('success', 'Instagram connected successfully! You can now import media.');
        window.history.replaceState({ module: 'connected-accounts' }, '', '/settings/connections');
        loadStatus();
      }
    } else if (igParam === 'error' || errCode) {
      const friendlyMsg = parseErrorMessage(errCode);
      showToast('error', friendlyMsg);
      window.history.replaceState({ module: 'connected-accounts' }, '', '/settings/connections');
    } else if (isAuthenticated) {
      loadStatus();
    }
  }, [isAuthenticated]);

  const loadStatus = async () => {
    setLoading(true);
    setApiError(null);
    try {
      const statusRes = await apiClient.getInstagramStatus();
      setIgStatus(statusRes);
    } catch (err: any) {
      console.error('Failed to load Instagram connection status:', err);
      setApiError(err.message || 'Unable to connect to Zynova backend server. Please verify network connectivity.');
    } finally {
      setLoading(false);
    }
  };

  const handleConnectInstagram = async () => {
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    setConnecting(true);
    setApiError(null);
    try {
      const res = await apiClient.getInstagramAuthorizeUrl('web');
      if (res.url) {
        window.location.href = res.url;
      }
    } catch (err: any) {
      setConnecting(false);
      const msg = err.message || 'Failed to initiate Meta OAuth authorization.';
      showToast('error', msg);
      setApiError(msg);
    }
  };

  const handleRefreshStatus = async () => {
    setRefreshing(true);
    try {
      await loadStatus();
      showToast('success', 'Instagram connection status refreshed.');
    } catch (err: any) {
      showToast('error', 'Failed to refresh status.');
    } finally {
      setRefreshing(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Are you sure you want to disconnect your Instagram account from Zynova?')) {
      return;
    }
    setLoading(true);
    try {
      await apiClient.disconnectInstagram();
      showToast('success', 'Instagram account disconnected successfully.');
      await loadStatus();
    } catch (err: any) {
      showToast('error', err.message || 'Failed to disconnect Instagram.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto w-full pb-16">
      {/* Top Breadcrumb & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl">
        <div>
          <button
            type="button"
            onClick={() => setActiveModule('settings')}
            className="inline-flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 font-semibold mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Settings Hub</span>
          </button>
          <div className="flex items-center space-x-2 text-rose-400 text-xs font-semibold uppercase tracking-wider">
            <InstagramIcon className="w-4 h-4" />
            <span>Third-Party Integrations</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Connected Accounts</h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage your sovereign connections to external creator platforms and social networks.
          </p>
        </div>

        {/* Dynamic Toast Banner */}
        {toast && (
          <div
            className={`p-3 px-4 rounded-2xl border text-xs flex items-center gap-2 animate-in fade-in max-w-sm ${
              toast.type === 'success'
                ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/20 border-rose-500/30 text-rose-300'
            }`}
          >
            {toast.type === 'success' ? (
              <Check className="w-4 h-4 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0" />
            )}
            <span className="leading-tight">{toast.message}</span>
          </div>
        )}
      </div>

      {/* Main Instagram Integration Card */}
      <div className="p-6 md:p-8 rounded-3xl bg-slate-900/70 border border-white/10 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/10">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-500 via-rose-500 to-purple-600 flex items-center justify-center text-white shadow-xl shadow-rose-500/20 shrink-0">
              <InstagramIcon className="w-8 h-8" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-lg font-bold text-white">Instagram</h2>
                {igStatus?.connected && igStatus.status === 'active' && (
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-[10px] font-bold uppercase tracking-wider">
                    Connected
                  </span>
                )}
                {igStatus?.connected && igStatus.status === 'needs_reconnect' && (
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-300 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Needs Reconnect
                  </span>
                )}
                {(!igStatus?.connected || igStatus.status === 'not_connected') && (
                  <span className="px-2.5 py-0.5 rounded-full bg-white/10 text-slate-400 text-[10px] font-bold uppercase tracking-wider">
                    Not Connected
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Meta Graph API v21.0 integration with Facebook Login
              </p>
            </div>
          </div>

          {igStatus?.connected && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRefreshStatus}
                disabled={refreshing}
                title="Refresh Status"
                className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          )}
        </div>

        {/* API Error State */}
        {apiError && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-3">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <div>
              <p className="font-semibold">Unable to reach Instagram services</p>
              <p className="text-[11px] text-rose-300/80 mt-0.5">{apiError}</p>
            </div>
          </div>
        )}

        {/* State 1: Needs Reconnect Warning */}
        {igStatus?.connected && igStatus.status === 'needs_reconnect' && (
          <div className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs space-y-3">
            <div className="flex items-center gap-2 font-bold text-amber-400">
              <AlertTriangle className="w-4 h-4" />
              <span>Instagram Authorization Expired or Revoked</span>
            </div>
            <p className="leading-relaxed">
              Your 60-day Meta Page access token has expired or was removed in your Facebook account settings. Please reconnect to resume syncing posts and reels.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={handleConnectInstagram}
                disabled={connecting}
                className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition"
              >
                {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <InstagramIcon className="w-4 h-4" />}
                <span>Reconnect Instagram</span>
              </button>
              <button
                type="button"
                onClick={handleDisconnect}
                className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs border border-white/10 transition"
              >
                Disconnect
              </button>
            </div>
          </div>
        )}

        {/* State 2: Connected Active State */}
        {igStatus?.connected && igStatus.status === 'active' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Instagram Handle</span>
                <p className="text-base font-bold text-white flex items-center gap-1.5">
                  <span>@{igStatus.username || 'unspecified'}</span>
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Synced Media</span>
                <p className="text-base font-bold text-white">
                  {igStatus.media_count !== null ? `${igStatus.media_count} Posts & Reels` : 'Available'}
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-1">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Last Status Check</span>
                <p className="text-xs font-medium text-slate-300 pt-1">
                  {igStatus.last_synced_at
                    ? new Date(igStatus.last_synced_at).toLocaleString()
                    : 'Recently'}
                </p>
              </div>
            </div>

            {/* Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsImportModalOpen(true)}
                  className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 via-rose-600 to-amber-600 hover:from-purple-500 hover:to-amber-500 text-white font-bold text-xs flex items-center gap-2 transition shadow-lg shadow-rose-500/20"
                >
                  <Download className="w-4 h-4" />
                  <span>Import Posts</span>
                </button>
                <button
                  type="button"
                  onClick={handleRefreshStatus}
                  disabled={refreshing}
                  className="px-3.5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold border border-white/10 flex items-center gap-1.5 transition"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                  <span>Refresh Status</span>
                </button>
              </div>

              <button
                type="button"
                onClick={handleDisconnect}
                disabled={loading}
                className="px-3.5 py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-semibold border border-rose-500/20 flex items-center gap-1.5 transition"
              >
                <Unlink className="w-3.5 h-3.5" />
                <span>Disconnect</span>
              </button>
            </div>
          </div>
        )}

        {/* State 3: Not Connected Initial State */}
        {(!igStatus?.connected || igStatus.status === 'not_connected') && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-2">
                <h4 className="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>What Zynova Reads</span>
                </h4>
                <ul className="text-xs text-slate-300 space-y-1.5 pl-4 list-disc">
                  <li>Your professional Instagram profile identifier and username</li>
                  <li>Published photos, videos, reels, and caption metadata</li>
                  <li>Total media counters and high-level engagement metrics</li>
                </ul>
              </div>

              <div className="p-4 rounded-2xl bg-black/40 border border-white/5 space-y-2">
                <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4" />
                  <span>What Zynova Never Does</span>
                </h4>
                <ul className="text-xs text-slate-300 space-y-1.5 pl-4 list-disc">
                  <li>We <strong>never</strong> post, comment, or like on your behalf</li>
                  <li>We <strong>never</strong> access your private direct messages (DMs)</li>
                  <li>We <strong>never</strong> expose your tokens or share data with advertisers</li>
                </ul>
              </div>
            </div>

            {/* Account Requirements Note */}
            <div className="p-4 rounded-2xl bg-slate-800/40 border border-white/5 flex items-start gap-3 text-xs text-slate-300">
              <Info className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
              <div className="leading-relaxed">
                <strong>Prerequisites for Instagram Integration:</strong> Per Meta Platform rules, you must have an <strong>Instagram Professional (Business or Creator)</strong> account linked to a <strong>Facebook Page</strong> that you administer. Personal Instagram accounts are not supported by the Meta Graph API.
              </div>
            </div>

            {/* Connect CTA Button */}
            <div className="pt-2">
              <button
                type="button"
                onClick={handleConnectInstagram}
                disabled={connecting || loading}
                className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-gradient-to-r from-purple-600 via-rose-600 to-amber-600 hover:from-purple-500 hover:to-amber-500 text-white font-bold text-sm flex items-center justify-center gap-2 transition shadow-xl shadow-rose-500/25 disabled:opacity-50"
              >
                {connecting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Connecting to Meta...</span>
                  </>
                ) : (
                  <>
                    <InstagramIcon className="w-4 h-4" />
                    <span>Connect Instagram</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Import Modal */}
      <InstagramImportModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onImportComplete={() => {
          showToast('success', 'Instagram media imported successfully into your feed!');
          loadStatus();
        }}
      />
    </div>
  );
};
