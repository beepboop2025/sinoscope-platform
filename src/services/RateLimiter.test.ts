import { describe, it, expect } from 'vitest';
import { createRateLimiter, canRequest, consumeToken, getTokens } from './RateLimiter';

describe('RateLimiter', () => {
  it('allows requests when tokens available', () => {
    createRateLimiter('test_provider', 5, 60000);
    expect(canRequest('test_provider')).toBe(true);
    expect(getTokens('test_provider')).toBe(5);
  });

  it('consumes tokens correctly', () => {
    createRateLimiter('test_consume', 3, 60000);
    consumeToken('test_consume');
    expect(getTokens('test_consume')).toBe(2);
    consumeToken('test_consume');
    consumeToken('test_consume');
    expect(getTokens('test_consume')).toBe(0);
    expect(canRequest('test_consume')).toBe(false);
  });

  it('does not go below zero', () => {
    createRateLimiter('test_floor', 1, 60000);
    consumeToken('test_floor');
    consumeToken('test_floor');
    expect(getTokens('test_floor')).toBe(0);
  });

  it('returns true for unknown provider', () => {
    expect(canRequest('unknown_provider')).toBe(true);
  });

  it('returns Infinity for unknown provider tokens', () => {
    expect(getTokens('unknown_xyz')).toBe(Infinity);
  });
});
