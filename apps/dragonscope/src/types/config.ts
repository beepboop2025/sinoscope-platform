export interface CacheEntry<T = unknown> {
  data: T;
  expiry: number;
}

export interface RateLimiterBucket {
  tokens: number;
  max: number;
  windowMs: number;
  lastRefill: number;
}

export interface TimezoneConfig {
  id: string;
  name: string;
  offset: number;
  abbreviation: string;
}
