import React from 'react';
import { Wifi, WifiOff, RefreshCw, AlertCircle, Clock } from 'lucide-react';
import { useOfflineSync } from '../../context/OfflineSyncContext';
import { useApp } from '../../context/AppContext';
import { t } from '../../i18n';

export const ConnectivityBadge: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { syncState, pendingCount, isOnline, triggerManualSync } = useOfflineSync();
  const { preferences } = useApp();

  if (syncState === 'online' && !compact) {
    return (
      <div 
        className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium cursor-default"
        title="Connected to SUPER_AI Backend"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        <Wifi className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{t('sync.online', preferences.language)}</span>
      </div>
    );
  }

  if (syncState === 'online' && compact) {
    return (
      <div 
        className="flex items-center justify-center w-7 h-7 rounded-full bg-emerald-500/10 text-emerald-400"
        title="Online"
      >
        <Wifi className="w-3.5 h-3.5" />
      </div>
    );
  }

  if (syncState === 'syncing') {
    return (
      <div 
        className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-medium animate-pulse"
        title="Synchronizing pending changes..."
      >
        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
        <span>{t('sync.syncing', preferences.language)}</span>
      </div>
    );
  }

  if (syncState === 'offline') {
    return (
      <button 
        onClick={triggerManualSync}
        className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/20 transition cursor-pointer"
        title="Working offline. Tap to retry connection."
      >
        <WifiOff className="w-3.5 h-3.5" />
        <span>{t('sync.offline', preferences.language)}</span>
      </button>
    );
  }

  if (syncState === 'sync_failed') {
    return (
      <button 
        onClick={triggerManualSync}
        className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-medium hover:bg-rose-500/20 transition cursor-pointer"
        title="Sync failed. Tap to retry."
      >
        <AlertCircle className="w-3.5 h-3.5" />
        <span>{t('sync.failed', preferences.language)}</span>
      </button>
    );
  }

  if (syncState === 'pending_changes') {
    return (
      <button 
        onClick={triggerManualSync}
        className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs font-medium hover:bg-sky-500/20 transition cursor-pointer"
        title={`${pendingCount} offline changes pending sync. Tap to sync now.`}
      >
        <Clock className="w-3.5 h-3.5" />
        <span>{pendingCount} Pending</span>
      </button>
    );
  }

  return null;
};
