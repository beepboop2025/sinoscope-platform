const memCache = new Map();

export function cacheGet(key) {
  const entry = memCache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiry) {
    memCache.delete(key);
    return null;
  }
  return entry.data;
}

export function cacheSet(key, data, ttlMs = 30000) {
  memCache.set(key, { data, expiry: Date.now() + ttlMs });
  if (memCache.size > 500) {
    const oldest = memCache.keys().next().value;
    memCache.delete(oldest);
  }
}

export function cacheClear(prefix) {
  if (!prefix) { memCache.clear(); return; }
  for (const key of memCache.keys()) {
    if (key.startsWith(prefix)) memCache.delete(key);
  }
}

export function cacheStats() {
  let active = 0;
  const now = Date.now();
  for (const entry of memCache.values()) {
    if (now <= entry.expiry) active++;
  }
  return { total: memCache.size, active };
}
