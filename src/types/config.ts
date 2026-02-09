export interface CacheEntry<T = unknown> {
  data: T;
  expiry: number;
  insertedAt: number;
}

export interface RateLimiterBucket {
  tokens: number;
  maxTokens: number;
  refillRate: number;
  refillInterval: number;
  lastRefill: number;
}

export interface TimezoneConfig {
  id: string;
  name: string;
  offset: number;
  abbreviation: string;
}
