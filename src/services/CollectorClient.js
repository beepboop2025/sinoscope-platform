/**
 * Client for the collector data server.
 * Fetches pre-collected data from /api/collector/{category}.json
 * with a 10s in-memory cache. Returns null on any failure (silent fallback).
 */

const cache = new Map();
const CACHE_TTL = 10_000; // 10 seconds

export async function getCollectorData(category) {
  const now = Date.now();
  const cached = cache.get(category);
  if (cached && (now - cached.time) < CACHE_TTL) {
    return cached.data;
  }

  try {
    const res = await fetch(`/api/collector/${category}.json`);
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
