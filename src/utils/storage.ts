import { openDB, type IDBPDatabase } from 'idb';
import type { StateStorage } from 'zustand/middleware';

/**
 * Single IndexedDB database for all local save data (settings, collection,
 * decks, currency, pack timers). Everything lives in one key/value object
 * store: each game system owns one key, and zustand's `persist` middleware
 * handles (de)serialization on top of this module.
 */
const DB_NAME = 'primordia';
const DB_VERSION = 1;
const KEYVAL_STORE = 'keyval';

let dbPromise: Promise<IDBPDatabase> | undefined;

function getDb(): Promise<IDBPDatabase> {
  dbPromise ??= openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(KEYVAL_STORE)) {
        db.createObjectStore(KEYVAL_STORE);
      }
    },
  });
  return dbPromise;
}

export async function getValue<T>(key: string): Promise<T | undefined> {
  const db = await getDb();
  return (await db.get(KEYVAL_STORE, key)) as T | undefined;
}

export async function setValue(key: string, value: unknown): Promise<void> {
  const db = await getDb();
  await db.put(KEYVAL_STORE, value, key);
}

export async function deleteValue(key: string): Promise<void> {
  const db = await getDb();
  await db.delete(KEYVAL_STORE, key);
}

/** Permanently erase the whole save. Used by Settings → "Reset save data". */
export async function wipeAllData(): Promise<void> {
  if (dbPromise !== undefined) {
    (await dbPromise).close();
    dbPromise = undefined;
  }
  await new Promise<void>((resolve, reject) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error ?? new Error('deleteDatabase failed'));
    // Another open connection blocks deletion; resolve anyway — the delete
    // completes as soon as that connection closes (we reload right after).
    request.onblocked = () => resolve();
  });
}

/** Adapter so zustand `persist` stores state in IndexedDB instead of localStorage. */
export const idbStateStorage: StateStorage = {
  getItem: async (name) => (await getValue<string>(name)) ?? null,
  setItem: (name, value) => setValue(name, value),
  removeItem: (name) => deleteValue(name),
};
