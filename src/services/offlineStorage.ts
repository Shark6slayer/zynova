/**
 * SUPER_AI IndexedDB Offline Persistence Layer
 * Database: super_ai_offline_db (Version: 1)
 *
 * Stores:
 * 1. post_drafts: User social post drafts (content, mediaUrl, tags, status, timestamps)
 * 2. public_cache: Cached public shopping catalog, restaurant lists, and menus
 * 3. action_queue: Offline mutations queue with idempotency keys and retry metadata
 */

export interface LocalPostDraft {
  id: string; // uuid
  userId: string; // isolates drafts per user (or 'guest' if unauthenticated)
  content: string;
  mediaUrl?: string;
  mediaType?: 'image' | 'video';
  tags?: string[];
  createdAt: string;
  updatedAt: string;
  status: 'draft' | 'publishing' | 'failed';
  lastError?: string;
}

export interface CachedPublicItem<T = any> {
  key: string; // e.g., 'catalog:products', 'catalog:restaurants', 'menu:rest_123'
  data: T;
  cachedAt: number; // unix timestamp in ms
  expiresAt: number; // unix timestamp in ms (e.g. 24h validity)
  itemType: 'products' | 'restaurants' | 'menu';
}

export interface QueuedOfflineAction {
  id: string; // uuid
  userId: string; // ownership isolation
  idempotencyKey: string; // unique idempotency key
  actionType: 'create_post' | 'like_post' | 'unlike_post';
  endpoint: string;
  method: 'POST' | 'PUT' | 'DELETE';
  payload: any;
  createdAt: number;
  attempts: number;
  maxAttempts: number;
  lastAttemptAt?: number;
  lastError?: string;
  status: 'pending' | 'processing' | 'failed' | 'conflict';
}

const DB_NAME = 'super_ai_offline_db';
const DB_VERSION = 1;

let dbPromise: Promise<IDBDatabase> | null = null;

export function getOfflineDB(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      reject(new Error('IndexedDB is not supported in this environment.'));
      return;
    }

    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = request.result;
      const oldVersion = event.oldVersion;

      // Schema Migration logic
      if (oldVersion < 1) {
        // Store 1: post_drafts
        if (!db.objectStoreNames.contains('post_drafts')) {
          const draftStore = db.createObjectStore('post_drafts', { keyPath: 'id' });
          draftStore.createIndex('by_user', 'userId', { unique: false });
          draftStore.createIndex('by_updated', 'updatedAt', { unique: false });
        }

        // Store 2: public_cache
        if (!db.objectStoreNames.contains('public_cache')) {
          const cacheStore = db.createObjectStore('public_cache', { keyPath: 'key' });
          cacheStore.createIndex('by_type', 'itemType', { unique: false });
          cacheStore.createIndex('by_expires', 'expiresAt', { unique: false });
        }

        // Store 3: action_queue
        if (!db.objectStoreNames.contains('action_queue')) {
          const queueStore = db.createObjectStore('action_queue', { keyPath: 'id' });
          queueStore.createIndex('by_user', 'userId', { unique: false });
          queueStore.createIndex('by_status', 'status', { unique: false });
          queueStore.createIndex('by_idempotency', 'idempotencyKey', { unique: true });
        }
      }
    };

    request.onsuccess = () => {
      resolve(request.result);
    };

    request.onerror = () => {
      console.error('IndexedDB open error:', request.error);
      reject(request.error);
    };

    request.onblocked = () => {
      console.warn('IndexedDB upgrade blocked by an open tab.');
    };
  });

  return dbPromise;
}

// -----------------------------------------------------------------------------
// POST DRAFTS SERVICE
// -----------------------------------------------------------------------------

export async function saveLocalDraft(draft: LocalPostDraft): Promise<void> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('post_drafts', 'readwrite');
      const store = tx.objectStore('post_drafts');
      const req = store.put(draft);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function getLocalDraftsByUser(userId: string): Promise<LocalPostDraft[]> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('post_drafts', 'readonly');
      const store = tx.objectStore('post_drafts');
      const index = store.index('by_user');
      const req = index.getAll(IDBKeyRange.only(userId));
      req.onsuccess = () => {
        const drafts = (req.result || []) as LocalPostDraft[];
        // Sort descending by updatedAt
        drafts.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
        resolve(drafts);
      };
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function getLocalDraftById(id: string): Promise<LocalPostDraft | null> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('post_drafts', 'readonly');
      const store = tx.objectStore('post_drafts');
      const req = store.get(id);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function deleteLocalDraft(id: string): Promise<void> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('post_drafts', 'readwrite');
      const store = tx.objectStore('post_drafts');
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function clearDraftsForUser(userId: string): Promise<void> {
  const drafts = await getLocalDraftsByUser(userId);
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('post_drafts', 'readwrite');
      const store = tx.objectStore('post_drafts');
      drafts.forEach((d) => store.delete(d.id));
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    } catch (e) {
      reject(e);
    }
  });
}

// -----------------------------------------------------------------------------
// PUBLIC DATA CACHE SERVICE (Products, Restaurants, Menus)
// -----------------------------------------------------------------------------

const DEFAULT_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

export async function setCachedPublicData<T>(
  key: string,
  data: T,
  itemType: 'products' | 'restaurants' | 'menu',
  ttlMs: number = DEFAULT_CACHE_TTL_MS
): Promise<void> {
  const db = await getOfflineDB();
  const now = Date.now();
  const cacheItem: CachedPublicItem<T> = {
    key,
    data,
    cachedAt: now,
    expiresAt: now + ttlMs,
    itemType,
  };

  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('public_cache', 'readwrite');
      const store = tx.objectStore('public_cache');
      const req = store.put(cacheItem);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function getCachedPublicData<T>(
  key: string
): Promise<{ data: T; cachedAt: number; isExpired: boolean } | null> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('public_cache', 'readonly');
      const store = tx.objectStore('public_cache');
      const req = store.get(key);
      req.onsuccess = () => {
        const item = req.result as CachedPublicItem<T> | undefined;
        if (!item) {
          resolve(null);
          return;
        }
        const isExpired = Date.now() > item.expiresAt;
        resolve({
          data: item.data,
          cachedAt: item.cachedAt,
          isExpired,
        });
      };
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function clearExpiredCache(): Promise<number> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('public_cache', 'readwrite');
      const store = tx.objectStore('public_cache');
      const req = store.getAll();
      req.onsuccess = () => {
        const items = req.result as CachedPublicItem[];
        const now = Date.now();
        let deleted = 0;
        for (const item of items) {
          if (now > item.expiresAt) {
            store.delete(item.key);
            deleted++;
          }
        }
        resolve(deleted);
      };
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

// -----------------------------------------------------------------------------
// ACTION QUEUE SERVICE (Offline Mutations with Idempotency)
// -----------------------------------------------------------------------------

export async function enqueueOfflineAction(action: Omit<QueuedOfflineAction, 'id' | 'createdAt' | 'attempts' | 'status'> & { id?: string }): Promise<QueuedOfflineAction> {
  const db = await getOfflineDB();

  // First check if an action with this idempotencyKey already exists
  const existing = await new Promise<QueuedOfflineAction | null>((resolve) => {
    try {
      const tx = db.transaction('action_queue', 'readonly');
      const store = tx.objectStore('action_queue');
      const index = store.index('by_idempotency');
      const req = index.getAll(IDBKeyRange.only(action.idempotencyKey));
      req.onsuccess = () => {
        const items = req.result as QueuedOfflineAction[];
        resolve(items && items.length > 0 ? items[0] : null);
      };
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });

  if (existing) {
    console.warn('Action with idempotency key already queued, ignoring duplicate:', action.idempotencyKey);
    return existing;
  }

  const fullAction: QueuedOfflineAction = {
    id: action.id || (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : 'act_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8)),
    createdAt: Date.now(),
    attempts: 0,
    status: 'pending',
    ...action,
  };

  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('action_queue', 'readwrite');
      const store = tx.objectStore('action_queue');
      const req = store.add(fullAction);
      req.onsuccess = () => resolve(fullAction);
      req.onerror = () => {
        // If error is ConstraintError, already queued (idempotency protection)
        if (req.error && req.error.name === 'ConstraintError') {
          console.warn('Action with idempotency key already queued, ignoring duplicate');
          resolve(fullAction);
        } else {
          reject(req.error);
        }
      };
    } catch (e) {
      reject(e);
    }
  });
}

export async function getPendingActionsByUser(userId: string): Promise<QueuedOfflineAction[]> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('action_queue', 'readonly');
      const store = tx.objectStore('action_queue');
      const index = store.index('by_user');
      const req = index.getAll(IDBKeyRange.only(userId));
      req.onsuccess = () => {
        const actions = (req.result || []) as QueuedOfflineAction[];
        // filter pending or processing
        resolve(actions.filter((a) => a.status === 'pending' || a.status === 'processing' || a.status === 'failed'));
      };
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function updateQueuedAction(action: QueuedOfflineAction): Promise<void> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('action_queue', 'readwrite');
      const store = tx.objectStore('action_queue');
      const req = store.put(action);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function deleteQueuedAction(id: string): Promise<void> {
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('action_queue', 'readwrite');
      const store = tx.objectStore('action_queue');
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  });
}

export async function quarantineOrClearUserActions(oldUserId: string): Promise<void> {
  const actions = await getPendingActionsByUser(oldUserId);
  const db = await getOfflineDB();
  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction('action_queue', 'readwrite');
      const store = tx.objectStore('action_queue');
      actions.forEach((a) => store.delete(a.id));
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    } catch (e) {
      reject(e);
    }
  });
}
