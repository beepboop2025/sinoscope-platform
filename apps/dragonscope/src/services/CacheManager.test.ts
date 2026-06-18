import { describe, it, expect, beforeEach, vi } from 'vitest';
import { cacheGet, cacheSet, cacheClear, cacheStats } from './CacheManager';

beforeEach(() => {
  cacheClear();
});

describe('cacheGet / cacheSet', () => {
  it('stores and retrieves data', () => {
    cacheSet('key1', { value: 42 }, 10000);
    expect(cacheGet('key1')).toEqual({ value: 42 });
  });
  it('returns null for missing key', () => {
    expect(cacheGet('nonexistent')).toBeNull();
  });
  it('returns null for expired entry', () => {
    cacheSet('exp', 'data', 1); // 1ms TTL
    return new Promise<void>(resolve => {
      setTimeout(() => {
        expect(cacheGet('exp')).toBeNull();
        resolve();
      }, 10);
    });
  });
});

describe('cacheClear', () => {
  it('clears all entries with no prefix', () => {
    cacheSet('a', 1);
    cacheSet('b', 2);
    cacheClear();
    expect(cacheGet('a')).toBeNull();
    expect(cacheGet('b')).toBeNull();
  });
  it('clears entries matching prefix', () => {
    cacheSet('stock_AAPL', 1);
    cacheSet('stock_MSFT', 2);
    cacheSet('crypto_BTC', 3);
    cacheClear('stock_');
    expect(cacheGet('stock_AAPL')).toBeNull();
    expect(cacheGet('crypto_BTC')).toEqual(3);
  });
});

describe('cacheStats', () => {
  it('returns correct counts', () => {
    cacheSet('a', 1, 60000);
    cacheSet('b', 2, 60000);
    const stats = cacheStats();
    expect(stats.total).toBe(2);
    expect(stats.active).toBe(2);
  });
});
