import { describe, it, expect } from 'vitest';
import { rand, randInt, randIntInclusive, clamp } from './math';

describe('rand', () => {
  it('returns value within range', () => {
    for (let i = 0; i < 100; i++) {
      const v = rand(1, 10);
      expect(v).toBeGreaterThanOrEqual(1);
      expect(v).toBeLessThanOrEqual(10);
    }
  });
  it('handles reversed bounds', () => {
    const v = rand(10, 1);
    expect(v).toBeGreaterThanOrEqual(1);
    expect(v).toBeLessThanOrEqual(10);
  });
  it('handles NaN bounds', () => {
    const v = rand(NaN, NaN);
    expect(v).toBe(0);
  });
});

describe('randInt', () => {
  it('returns integer within range', () => {
    for (let i = 0; i < 100; i++) {
      const v = randInt(1, 10);
      expect(Number.isInteger(v)).toBe(true);
      expect(v).toBeGreaterThanOrEqual(1);
      expect(v).toBeLessThan(10);
    }
  });
  it('handles equal bounds', () => {
    expect(randInt(5, 5)).toBe(5);
  });
});

describe('randIntInclusive', () => {
  it('returns integer within inclusive range', () => {
    for (let i = 0; i < 100; i++) {
      const v = randIntInclusive(1, 5);
      expect(Number.isInteger(v)).toBe(true);
      expect(v).toBeGreaterThanOrEqual(1);
      expect(v).toBeLessThanOrEqual(5);
    }
  });
});

describe('clamp', () => {
  it('clamps value within bounds', () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-1, 0, 10)).toBe(0);
    expect(clamp(15, 0, 10)).toBe(10);
  });
});
