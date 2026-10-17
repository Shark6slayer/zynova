import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './AuthContext';
import { 
  getPendingActionsByUser, 
  updateQueuedAction, 
  deleteQueuedAction, 
  quarantineOrClearUserActions,
  type QueuedOfflineAction 
} from '../services/offlineStorage';
import { apiClient } from '../services/apiClient';

export type SyncState = 'online' | 'offline' | 'syncing' | 'sync_failed' | 'pending_changes';

interface OfflineSyncContextType {
  isOnline: boolean;
  syncState: SyncState;
  pendingCount: number;
  lastSyncTime: number | null;
  syncError: string | null;
  triggerManualSync: () => Promise<void>;
  refreshPendingCount: () => Promise<void>;
}

const OfflineSyncContext = createContext<OfflineSyncContextType | undefined>(undefined);

export const OfflineSyncProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const currentUserId = user?.id || 'guest';

  const [isOnline, setIsOnline] = useState<boolean>(() => {
    return typeof navigator !== 'undefined' ? navigator.onLine : true;
  });
  const [syncState, setSyncState] = useState<SyncState>('online');
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [lastSyncTime, setLastSyncTime] = useState<number | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const isSyncWorkerRunning = useRef(false);
  const previousUserId = useRef<string>(currentUserId);

  // Refresh pending count
  const refreshPendingCount = useCallback(async () => {
    try {
      const actions = await getPendingActionsByUser(currentUserId);
      const count = actions.filter((a) => a.status === 'pending' || a.status === 'failed').length;
      setPendingCount(count);
      return;
    } catch {
      // IndexedDB might not be supported in test or restricted environment
    }
  }, [currentUserId]);

  // Account switching security isolation: Quarantine/clear pending items of old user
  useEffect(() => {
    if (previousUserId.current !== currentUserId) {
      const oldId = previousUserId.current;
      previousUserId.current = currentUserId;
      if (oldId && oldId !== 'guest') {
        quarantineOrClearUserActions(oldId).catch((err) => {
          console.warn('Failed to quarantine old user queue on account switch:', err);
        });
      }
      refreshPendingCount();
    }
  }, [currentUserId, refreshPendingCount]);

  // Reliable sync execution worker with exponential backoff & idempotency protection
  const processQueue = useCallback(async () => {
    if (isSyncWorkerRunning.current) {
      console.log('Sync worker already active, skipping duplicate worker launch');
      return;
    }
    if (!navigator.onLine || !isAuthenticated || currentUserId === 'guest') {
      return;
    }

    isSyncWorkerRunning.current = true;
    setSyncState('syncing');
    setSyncError(null);

    try {
      const actions = await getPendingActionsByUser(currentUserId);
      const actionable = actions.filter((a) => a.status === 'pending' || a.status === 'failed');

      if (actionable.length === 0) {
        setSyncState('online');
        setPendingCount(0);
        return;
      }

      let hadFailures = false;

      for (const action of actionable) {
        // Enforce max attempts
        if (action.attempts >= action.maxAttempts) {
          action.status = 'failed';
          action.lastError = 'Max retry attempts exceeded';
          await updateQueuedAction(action);
          hadFailures = true;
          continue;
        }

        // Exponential backoff check with jitter: 2^attempts * 1000ms
        const now = Date.now();
        if (action.lastAttemptAt) {
          const backoffDelay = Math.pow(2, action.attempts) * 1000 + Math.random() * 500;
          if (now - action.lastAttemptAt < backoffDelay) {
            // Not ready to retry yet
            continue;
          }
        }

        action.status = 'processing';
        action.attempts += 1;
        action.lastAttemptAt = now;
        await updateQueuedAction(action);

        try {
          // Re-check authentication
          const token = apiClient.getToken();
          if (!token) {
            action.status = 'failed';
            action.lastError = 'Authentication required to process offline queue';
            await updateQueuedAction(action);
            hadFailures = true;
            break;
          }

          // Execute supported idempotent mutations
          if (action.actionType === 'create_post') {
            await apiClient.createSocialPost({
              ...action.payload,
              idempotency_key: action.idempotencyKey,
            });
            await deleteQueuedAction(action.id);
          } else if (action.actionType === 'like_post') {
            await apiClient.likeSocialPost(action.payload.postId);
            await deleteQueuedAction(action.id);
          } else if (action.actionType === 'unlike_post') {
            await apiClient.unlikeSocialPost(action.payload.postId);
            await deleteQueuedAction(action.id);
          } else {
            // Unknown or unallowed action type (e.g. Orders/Payments are strictly prohibited from offline queue)
            action.status = 'failed';
            action.lastError = `Action type ${action.actionType} is not permitted for offline execution`;
            await updateQueuedAction(action);
            hadFailures = true;
          }
        } catch (err: any) {
          console.error('Queue execution failed for item:', action.id, err);
          action.status = 'failed';
          action.lastError = err?.message || 'Network or server error';
          await updateQueuedAction(action);
          hadFailures = true;
        }
      }

      await refreshPendingCount();
      setLastSyncTime(Date.now());

      if (hadFailures) {
        setSyncState('sync_failed');
        setSyncError('Some pending changes could not be synchronized.');
      } else {
        const remaining = await getPendingActionsByUser(currentUserId);
        const count = remaining.filter((a) => a.status === 'pending' || a.status === 'failed').length;
        setSyncState(count > 0 ? 'pending_changes' : 'online');
      }
    } catch (err: any) {
      setSyncState('sync_failed');
      setSyncError(err?.message || 'Sync worker encountered an error.');
    } finally {
      isSyncWorkerRunning.current = false;
    }
  }, [currentUserId, isAuthenticated, refreshPendingCount]);

  // Connectivity event listeners & periodic ping to /api/v1/health
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Double check real backend connectivity
      apiClient.checkHealth()
        .then(() => {
          setIsOnline(true);
          processQueue();
        })
        .catch(() => {
          // navigator says online but backend is unreachable
          setIsOnline(false);
          setSyncState('offline');
        });
    };

    const handleOffline = () => {
      setIsOnline(false);
      setSyncState('offline');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial check
    refreshPendingCount();

    // Heartbeat ping every 30 seconds
    const interval = setInterval(() => {
      if (navigator.onLine) {
        apiClient.checkHealth()
          .then(() => {
            if (!isOnline) {
              setIsOnline(true);
              processQueue();
            }
          })
          .catch(() => {
            if (isOnline) {
              setIsOnline(false);
              setSyncState('offline');
            }
          });
      } else {
        setIsOnline(false);
        setSyncState('offline');
      }
    }, 30000);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, [isOnline, processQueue, refreshPendingCount]);

  // Adjust syncState on pendingCount change
  useEffect(() => {
    if (!isOnline) {
      setSyncState('offline');
    } else if (pendingCount > 0 && syncState !== 'syncing' && syncState !== 'sync_failed') {
      setSyncState('pending_changes');
    } else if (pendingCount === 0 && syncState !== 'syncing') {
      setSyncState('online');
    }
  }, [isOnline, pendingCount, syncState]);

  const triggerManualSync = async () => {
    if (!isOnline) {
      // Attempt health check first
      try {
        await apiClient.checkHealth();
        setIsOnline(true);
      } catch {
        setSyncState('offline');
        return;
      }
    }
    await processQueue();
  };

  return (
    <OfflineSyncContext.Provider
      value={{
        isOnline,
        syncState,
        pendingCount,
        lastSyncTime,
        syncError,
        triggerManualSync,
        refreshPendingCount,
      }}
    >
      {children}
    </OfflineSyncContext.Provider>
  );
};

export const useOfflineSync = () => {
  const context = useContext(OfflineSyncContext);
  if (!context) {
    throw new Error('useOfflineSync must be used within an OfflineSyncProvider');
  }
  return context;
};
