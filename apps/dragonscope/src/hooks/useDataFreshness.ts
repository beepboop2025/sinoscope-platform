/**
 * useDataFreshness — tracks when data was last updated and triggers auto-refresh.
 *
 * Returns freshness state (color-coded) and a `markFresh()` callback to call
 * whenever new data arrives.
 *
 * Color coding:
 *   - green:  < 30 seconds
 *   - amber:  30s – 2 minutes
 *   - red:    > 2 minutes (stale)
 */

import { useState, useRef, useCallback, useEffect } from 'react';

type FreshnessLevel = 'fresh' | 'aging' | 'stale' | 'unknown';

interface DataFreshnessState {
  lastUpdated: number | null;
  secondsAgo: number;
  level: FreshnessLevel;
  color: string;
  label: string;
}

interface UseDataFreshnessOptions {
  /** Auto-refresh callback when data becomes stale (> staleAfterMs) */
  onStale?: () => void;
  /** Milliseconds before data is considered stale (default: 120_000 = 2 min) */
  staleAfterMs?: number;
  /** How often to re-evaluate freshness (default: 5000ms) */
  tickMs?: number;
}

interface UseDataFreshnessReturn extends DataFreshnessState {
  markFresh: () => void;
}

function computeState(lastUpdated: number | null): DataFreshnessState {
  if (!lastUpdated) {
    return { lastUpdated: null, secondsAgo: Infinity, level: 'unknown', color: 'var(--text-4)', label: 'No data' };
  }
  const secondsAgo = Math.round((Date.now() - lastUpdated) / 1000);
  if (secondsAgo < 30) {
    return { lastUpdated, secondsAgo, level: 'fresh', color: 'var(--green)', label: `${secondsAgo}s ago` };
  }
  if (secondsAgo < 120) {
    return { lastUpdated, secondsAgo, level: 'aging', color: 'var(--amber)', label: `${Math.round(secondsAgo / 60)}m ${secondsAgo % 60}s ago` };
  }
  const mins = Math.round(secondsAgo / 60);
  return { lastUpdated, secondsAgo, level: 'stale', color: 'var(--red)', label: `${mins}m ago` };
}

export function useDataFreshness(options: UseDataFreshnessOptions = {}): UseDataFreshnessReturn {
  const { onStale, staleAfterMs = 120_000, tickMs = 5000 } = options;
  const lastUpdatedRef = useRef<number | null>(null);
  const staleFiredRef = useRef(false);
  const [state, setState] = useState<DataFreshnessState>(() => computeState(null));

  const markFresh = useCallback(() => {
    const now = Date.now();
    lastUpdatedRef.current = now;
    staleFiredRef.current = false;
    setState(computeState(now));
  }, []);

  // Periodic freshness re-evaluation
  useEffect(() => {
    const id = setInterval(() => {
      const ts = lastUpdatedRef.current;
      setState(computeState(ts));

      // Trigger auto-refresh when stale
      if (ts && !staleFiredRef.current && (Date.now() - ts) > staleAfterMs) {
        staleFiredRef.current = true;
        onStale?.();
      }
    }, tickMs);
    return () => clearInterval(id);
  }, [onStale, staleAfterMs, tickMs]);

  return { ...state, markFresh };
}

/**
 * useGlobalFreshness — aggregate freshness across multiple data sources.
 * Feed it an array of timestamps and it returns the worst-case freshness.
 */
export function useGlobalFreshness(timestamps: (number | null | undefined)[]): DataFreshnessState {
  const [state, setState] = useState<DataFreshnessState>(() => computeState(null));

  useEffect(() => {
    function update() {
      const validTs = timestamps.filter((t): t is number => typeof t === 'number' && t > 0);
      if (validTs.length === 0) {
        setState(computeState(null));
        return;
      }
      // Use the OLDEST (worst-case) timestamp
      const oldest = Math.min(...validTs);
      setState(computeState(oldest));
    }

    update();
    const id = setInterval(update, 5000);
    return () => clearInterval(id);
  }, [timestamps.join(',')]);

  return state;
}
