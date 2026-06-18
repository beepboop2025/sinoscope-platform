import type { RateLimiterBucket } from '../types/config';

const buckets: Record<string, RateLimiterBucket> = {};

export function createRateLimiter(provider: string, maxRequests: number, windowMs: number): void {
  buckets[provider] = { tokens: maxRequests, max: maxRequests, windowMs, lastRefill: Date.now() };
}

function refillIfNeeded(b: RateLimiterBucket): void {
  const elapsed = Date.now() - b.lastRefill;
  if (elapsed >= b.windowMs) {
    b.tokens = b.max;
    b.lastRefill = Date.now();
  }
}

export function canRequest(provider: string): boolean {
  const b = buckets[provider];
  if (!b) return true;
  refillIfNeeded(b);
  return b.tokens > 0;
}

export function consumeToken(provider: string): void {
  const b = buckets[provider];
  if (!b) return;
  refillIfNeeded(b);
  b.tokens = Math.max(0, b.tokens - 1);
}

export function getTokens(provider: string): number {
  const b = buckets[provider];
  if (!b) return Infinity;
  refillIfNeeded(b);
  return b.tokens;
}

// Simple backend request throttle — the backend handles per-provider rate limits
createRateLimiter('backend', 200, 60000);
