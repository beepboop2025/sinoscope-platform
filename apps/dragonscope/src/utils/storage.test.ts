import { describe, it, expect, beforeEach } from 'vitest';
import { safeJsonParse, storageRead, storageWrite } from './storage';

describe('safeJsonParse', () => {
  it('parses valid JSON', () => {
    expect(safeJsonParse('{"a":1}')).toEqual({ a: 1 });
  });
  it('returns fallback for invalid JSON', () => {
    expect(safeJsonParse('not json', 'default')).toBe('default');
  });
  it('returns fallback for null/undefined', () => {
    expect(safeJsonParse(null)).toBe(null);
    expect(safeJsonParse(undefined, [])).toEqual([]);
  });
  it('returns fallback for non-string', () => {
    expect(safeJsonParse(123, 'fallback')).toBe('fallback');
  });
});

describe('storageRead', () => {
  beforeEach(() => { localStorage.clear(); });
  it('reads stored value', () => {
    localStorage.setItem('test', JSON.stringify({ foo: 'bar' }));
    expect(storageRead('test')).toEqual({ foo: 'bar' });
  });
  it('returns fallback for missing key', () => {
    expect(storageRead('missing', 'default')).toBe('default');
  });
});

describe('storageWrite', () => {
  beforeEach(() => { localStorage.clear(); });
  it('writes and returns true', () => {
    expect(storageWrite('key', { a: 1 })).toBe(true);
    expect(JSON.parse(localStorage.getItem('key')!)).toEqual({ a: 1 });
  });
});
