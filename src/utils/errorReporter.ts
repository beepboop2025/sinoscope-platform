/**
 * Lightweight error reporter for production.
 * Batches errors and sends them to a server endpoint.
 * In dev mode, tracks error counts for the UI footer counter.
 */

interface ErrorReport {
  message: string;
  stack?: string;
  component?: string;
  timestamp: number;
  url: string;
  userAgent: string;
  sessionDuration: number;
  viewportSize: string;
}

const ERROR_ENDPOINT = '/api/errors';
const BATCH_INTERVAL = 5000;
const MAX_BATCH_SIZE = 10;
const ERROR_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

let errorQueue: ErrorReport[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
const sessionStart = Date.now();

/** Recent error timestamps for the dev-mode counter (last 5 minutes) */
let recentErrorTimestamps: number[] = [];
let errorCountListeners: Array<(count: number) => void> = [];

function createReport(error: Error | string, component?: string): ErrorReport {
  const err = typeof error === 'string' ? new Error(error) : error;
  return {
    message: err.message,
    stack: err.stack?.slice(0, 1000),
    component,
    timestamp: Date.now(),
    url: window.location.href,
    userAgent: navigator.userAgent,
    sessionDuration: Math.round((Date.now() - sessionStart) / 1000),
    viewportSize: `${window.innerWidth}x${window.innerHeight}`,
  };
}

function pruneOldErrors(): void {
  const cutoff = Date.now() - ERROR_WINDOW_MS;
  recentErrorTimestamps = recentErrorTimestamps.filter(ts => ts > cutoff);
}

function notifyCountListeners(): void {
  pruneOldErrors();
  const count = recentErrorTimestamps.length;
  for (const fn of errorCountListeners) {
    try { fn(count); } catch { /* ignore */ }
  }
}

/** Get the number of errors in the last 5 minutes */
export function getRecentErrorCount(): number {
  pruneOldErrors();
  return recentErrorTimestamps.length;
}

/** Subscribe to error count changes (for UI components) */
export function onErrorCountChange(fn: (count: number) => void): () => void {
  errorCountListeners.push(fn);
  return () => {
    errorCountListeners = errorCountListeners.filter(l => l !== fn);
  };
}

function flushQueue(): void {
  if (errorQueue.length === 0) return;

  const batch = errorQueue.splice(0, MAX_BATCH_SIZE);
  try {
    // Use sendBeacon for reliability (works during page unload)
    const sent = navigator.sendBeacon(
      ERROR_ENDPOINT,
      JSON.stringify({ errors: batch })
    );
    if (!sent) {
      // Fallback to fetch
      fetch(ERROR_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ errors: batch }),
      }).catch(() => {
        // Silently drop — we can't recurse into error reporting
      });
    }
  } catch {
    // Silently drop
  }
}

function scheduleFlush(): void {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flushQueue();
  }, BATCH_INTERVAL);
}

export function reportError(error: Error | string, component?: string): void {
  // Always track for the dev-mode counter
  recentErrorTimestamps.push(Date.now());
  notifyCountListeners();

  if (import.meta.env.DEV) {
    console.error('[ErrorReporter]', error, component);
    return;
  }

  errorQueue.push(createReport(error, component));
  if (errorQueue.length >= MAX_BATCH_SIZE) {
    flushQueue();
  } else {
    scheduleFlush();
  }
}

/** Install global error handlers. Call once at app startup. */
export function installGlobalErrorHandlers(): void {
  window.onerror = (_msg, _source, _line, _col, error) => {
    if (error) reportError(error, 'window.onerror');
  };

  window.onunhandledrejection = (event: PromiseRejectionEvent) => {
    const error = event.reason instanceof Error
      ? event.reason
      : String(event.reason);
    reportError(error, 'unhandledrejection');
  };

  // Flush on page unload
  window.addEventListener('beforeunload', flushQueue);
}
