/**
 * Lightweight error reporter for production.
 * Batches errors and sends them to a server endpoint.
 */

interface ErrorReport {
  message: string;
  stack?: string;
  component?: string;
  timestamp: number;
  url: string;
  userAgent: string;
}

const ERROR_ENDPOINT = '/api/errors';
const BATCH_INTERVAL = 5000;
const MAX_BATCH_SIZE = 10;

let errorQueue: ErrorReport[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function createReport(error: Error | string, component?: string): ErrorReport {
  const err = typeof error === 'string' ? new Error(error) : error;
  return {
    message: err.message,
    stack: err.stack?.slice(0, 1000),
    component,
    timestamp: Date.now(),
    url: window.location.href,
    userAgent: navigator.userAgent,
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
