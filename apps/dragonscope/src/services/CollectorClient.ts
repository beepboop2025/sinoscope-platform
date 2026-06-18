/**
 * Client for the collector data server.
 * Fetches pre-collected data from /api/data/{category}
 * with a 10s in-memory cache. Returns null on any failure (silent fallback).
 */

interface CollectorCacheEntry {
  data: unknown;
  time: number;
}

const cache: Map<string, CollectorCacheEntry> = new Map();
const CACHE_TTL: number = 10_000; // 10 seconds
const FETCH_TIMEOUT: number = 15_000; // 15 second timeout (backend may call external APIs)
const API_BASE: string = import.meta.env.VITE_API_BASE_URL || '';

export async function getCollectorData(category: string): Promise<unknown> {
  const now: number = Date.now();
  const cached: CollectorCacheEntry | undefined = cache.get(category);
  if (cached && (now - cached.time) < CACHE_TTL) {
    return cached.data;
  }

  try {
    const controller = new AbortController();
    const timeoutId: ReturnType<typeof setTimeout> = setTimeout(() => controller.abort(), FETCH_TIMEOUT);
    const res: Response = await fetch(`${API_BASE}/api/data/${category}`, { signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) return null;
    const json: { data?: unknown } = await res.json();
    const data: unknown = json.data ?? null;
    if (data !== null) {
      cache.set(category, { data, time: now });
    }
    return data;
  } catch {
    return null;
  }
}
