const buckets = {};

export function createRateLimiter(provider, maxRequests, windowMs) {
  buckets[provider] = { tokens: maxRequests, max: maxRequests, windowMs, lastRefill: Date.now() };
}

function refillIfNeeded(b) {
  const elapsed = Date.now() - b.lastRefill;
  if (elapsed >= b.windowMs) {
    b.tokens = b.max;
    b.lastRefill = Date.now();
  }
}

export function canRequest(provider) {
  const b = buckets[provider];
  if (!b) return true;
  refillIfNeeded(b);
  return b.tokens > 0;
}

export function consumeToken(provider) {
  const b = buckets[provider];
  if (!b) return;
  refillIfNeeded(b);
  b.tokens = Math.max(0, b.tokens - 1);
}

export function getTokens(provider) {
  const b = buckets[provider];
  if (!b) return Infinity;
  refillIfNeeded(b);
  return b.tokens;
}

// Initialize default rate limits
createRateLimiter('frankfurter', 30, 60000);
createRateLimiter('coingecko', 25, 60000);
createRateLimiter('fmp', 240, 86400000);
createRateLimiter('fred', 100, 60000);
createRateLimiter('finnhub', 55, 60000);
createRateLimiter('gnews', 90, 86400000);
createRateLimiter('yahoo', 50, 60000);
createRateLimiter('alphavantage', 24, 86400000);
createRateLimiter('newsdata', 15, 86400000);       // ~500/month ≈ 15/day
createRateLimiter('newsapiorg', 90, 86400000);      // 100 calls/day
createRateLimiter('worldnews', 50, 86400000);       // free tier
