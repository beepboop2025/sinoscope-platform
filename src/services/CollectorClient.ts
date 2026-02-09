/**
 * Client for the collector data server.
 * Fetches pre-collected data from /api/data/{category}
 * with a 10s in-memory cache. Returns null on any failure (silent fallback).
 */

const cache = new Map();
const CACHE_TTL = 10_000; // 10 seconds
const FETCH_TIMEOUT = 8_000; // 8 second timeout

export async function getCollectorData(category) {
  const now = Date.now();
  const cached = cache.get(category);
  if (cached && (now - cached.time) < CACHE_TTL) {
    return cached.data;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT);
    const res = await fetch(`/api/data/${category}`, { signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) return null;
    const json = await res.json();
    const data = json.data ?? null;
    if (data !== null) {
      cache.set(category, { data, time: now });
    }
    return data;
  } catch {
    return null;
  }
}
