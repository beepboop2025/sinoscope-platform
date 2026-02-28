import type { CacheEntry } from '../types/config';

const memCache: Map<string, CacheEntry> = new Map();
const MAX_SIZE: number = 500;

export function cacheGet<T>(key: string): T | null {
  const entry = memCache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiry) {
    memCache.delete(key);
    return null;
  }
  return entry.data as T;
}

export function cacheSet(key: string, data: unknown, ttlMs: number = 30000): void {
  memCache.set(key, { data, expiry: Date.now() + ttlMs });

  if (memCache.size > MAX_SIZE) {
    // Evict expired entries first
    const now = Date.now();
    for (const [k, v] of memCache) {
      if (now > v.expiry) memCache.delete(k);
    }
    // If still over limit, evict oldest entries by insertion order
    if (memCache.size > MAX_SIZE) {
      const toDelete = memCache.size - MAX_SIZE;
      let deleted = 0;
      for (const k of memCache.keys()) {
        if (deleted >= toDelete) break;
        memCache.delete(k);
        deleted++;
      }
    }
  }
}

export function cacheClear(prefix?: string): void {
  if (!prefix) { memCache.clear(); return; }
  for (const key of memCache.keys()) {
    if (key.startsWith(prefix)) memCache.delete(key);
  }
}

export function cacheStats(): { total: number; active: number } {
  let active = 0;
  const now = Date.now();
  for (const entry of memCache.values()) {
    if (now <= entry.expiry) active++;
  }
  return { total: memCache.size, active };
}
