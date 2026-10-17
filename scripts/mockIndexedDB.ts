/**
 * Lightweight in-memory IndexedDB mock for Node.js test environment
 * Implements core IDBDatabase, IDBTransaction, IDBObjectStore, and IDBIndex contracts
 */

class MockIDBRequest {
  result: any = null;
  error: any = null;
  onsuccess: any = null;
  onerror: any = null;

  triggerSuccess(val: any) {
    this.result = val;
    if (this.onsuccess) this.onsuccess({ target: this });
  }

  triggerError(err: any) {
    this.error = err;
    if (this.onerror) this.onerror({ target: this });
  }
}

class MockIndex {
  name: string;
  keyPath: string;
  store: MockObjectStore;

  constructor(name: string, keyPath: string, store: MockObjectStore) {
    this.name = name;
    this.keyPath = keyPath;
    this.store = store;
  }

  getAll(query?: any): MockIDBRequest {
    const req = new MockIDBRequest();
    setTimeout(() => {
      const all = Array.from(this.store.records.values());
      if (query !== undefined) {
        const val = query?.lower !== undefined ? query.lower : query;
        const filtered = all.filter((r) => r[this.keyPath] === val);
        req.triggerSuccess(filtered);
      } else {
        req.triggerSuccess(all);
      }
    }, 0);
    return req;
  }
}

class MockObjectStore {
  name: string;
  keyPath: string;
  records = new Map<string, any>();
  indexes = new Map<string, MockIndex>();

  constructor(name: string, options: { keyPath: string }) {
    this.name = name;
    this.keyPath = options.keyPath;
  }

  createIndex(name: string, keyPath: string, _options?: any) {
    const idx = new MockIndex(name, keyPath, this);
    this.indexes.set(name, idx);
    return idx;
  }

  index(name: string): MockIndex {
    const idx = this.indexes.get(name);
    if (!idx) throw new Error(`Index ${name} not found`);
    return idx;
  }

  put(val: any): MockIDBRequest {
    const req = new MockIDBRequest();
    setTimeout(() => {
      const key = val[this.keyPath];
      this.records.set(key, JSON.parse(JSON.stringify(val)));
      req.triggerSuccess(key);
    }, 0);
    return req;
  }

  add(val: any): MockIDBRequest {
    const req = new MockIDBRequest();
    setTimeout(() => {
      const key = val[this.keyPath];
      if (this.records.has(key)) {
        req.triggerError({ name: 'ConstraintError', message: 'Key already exists' });
      } else {
        this.records.set(key, JSON.parse(JSON.stringify(val)));
        req.triggerSuccess(key);
      }
    }, 0);
    return req;
  }

  get(key: string): MockIDBRequest {
    const req = new MockIDBRequest();
    setTimeout(() => {
      const val = this.records.get(key);
      req.triggerSuccess(val ? JSON.parse(JSON.stringify(val)) : undefined);
    }, 0);
    return req;
  }

  getAll(): MockIDBRequest {
    const req = new MockIDBRequest();
    setTimeout(() => {
      const all = Array.from(this.records.values()).map(v => JSON.parse(JSON.stringify(v)));
      req.triggerSuccess(all);
    }, 0);
    return req;
  }

  delete(key: string): MockIDBRequest {
    const req = new MockIDBRequest();
    setTimeout(() => {
      this.records.delete(key);
      req.triggerSuccess(undefined);
    }, 0);
    return req;
  }
}

class MockTransaction {
  db: MockIDBDatabase;
  storeNames: string[];
  mode: string;
  oncomplete: any = null;
  onerror: any = null;

  constructor(db: MockIDBDatabase, storeNames: string | string[], mode: string) {
    this.db = db;
    this.storeNames = Array.isArray(storeNames) ? storeNames : [storeNames];
    this.mode = mode;
    setTimeout(() => {
      if (this.oncomplete) this.oncomplete();
    }, 10);
  }

  objectStore(name: string): MockObjectStore {
    return this.db.stores.get(name)!;
  }
}

class MockIDBDatabase {
  name: string;
  version: number;
  stores = new Map<string, MockObjectStore>();

  constructor(name: string, version: number) {
    this.name = name;
    this.version = version;
  }

  get objectStoreNames() {
    const names = Array.from(this.stores.keys());
    return {
      contains: (n: string) => names.includes(n),
      length: names.length,
      item: (i: number) => names[i],
    };
  }

  createObjectStore(name: string, options: { keyPath: string }) {
    const s = new MockObjectStore(name, options);
    this.stores.set(name, s);
    return s;
  }

  transaction(stores: string | string[], mode: string = 'readonly') {
    return new MockTransaction(this, stores, mode);
  }
}

class MockIDBFactory {
  databases = new Map<string, MockIDBDatabase>();

  open(name: string, version: number = 1): any {
    const req: any = {
      result: null,
      error: null,
      onsuccess: null,
      onerror: null,
      onupgradeneeded: null,
    };

    setTimeout(() => {
      let db = this.databases.get(name);
      const isNew = !db;
      if (!db) {
        db = new MockIDBDatabase(name, version);
        this.databases.set(name, db);
      }

      req.result = db;
      if (isNew && req.onupgradeneeded) {
        req.onupgradeneeded({ oldVersion: 0, newVersion: version, result: db });
      }
      if (req.onsuccess) {
        req.onsuccess({ target: req });
      }
    }, 0);

    return req;
  }
}

// Attach polyfill to global scope for testing
(global as any).window = global;
(global as any).indexedDB = new MockIDBFactory();
(global as any).IDBKeyRange = {
  only: (val: any) => ({ lower: val, upper: val }),
};
