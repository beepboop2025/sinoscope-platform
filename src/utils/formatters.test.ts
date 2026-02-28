import { describe, it, expect } from 'vitest';
import { formatPrice, formatPct, formatVolume, formatBps, formatCurrency, formatChange, formatChangePct } from './formatters';

describe('formatPrice', () => {
  it('formats small numbers with decimals', () => {
    expect(formatPrice(1.5)).toBe('1.50');
    expect(formatPrice(0.123, 3)).toBe('0.123');
  });
  it('formats thousands with K suffix', () => {
    expect(formatPrice(1500)).toBe('1.50K');
    expect(formatPrice(9999)).toBe('10.00K');
  });
  it('formats millions with M suffix', () => {
    expect(formatPrice(1500000)).toBe('1.50M');
  });
  it('formats billions with B suffix', () => {
    expect(formatPrice(2500000000)).toBe('2.50B');
  });
  it('handles null/undefined/NaN as 0', () => {
    expect(formatPrice(null)).toBe('0.00');
    expect(formatPrice(undefined)).toBe('0.00');
    expect(formatPrice('abc')).toBe('0.00');
  });
  it('handles negative values', () => {
    expect(formatPrice(-1500)).toBe('-1.50K');
  });
});

describe('formatPct', () => {
  it('formats percentage', () => {
    expect(formatPct(5.123)).toBe('5.12%');
    expect(formatPct(-2.7)).toBe('-2.70%');
  });
  it('handles null', () => {
    expect(formatPct(null)).toBe('0.00%');
  });
});

describe('formatVolume', () => {
  it('formats volume with suffix', () => {
    expect(formatVolume(1500000000)).toBe('1.5B');
    expect(formatVolume(2500000)).toBe('2.5M');
    expect(formatVolume(5000)).toBe('5.0K');
    expect(formatVolume(500)).toBe('500');
  });
});

describe('formatBps', () => {
  it('formats basis points', () => {
    expect(formatBps(25)).toBe('25bps');
    expect(formatBps(null)).toBe('0bps');
  });
});

describe('formatCurrency', () => {
  it('adds currency symbol', () => {
    expect(formatCurrency(100, 'USD')).toBe('$100.00');
    expect(formatCurrency(100, 'EUR')).toBe('\u20AC100.00');
    expect(formatCurrency(100, 'GBP')).toBe('\u00A3100.00');
  });
  it('handles unknown currency', () => {
    expect(formatCurrency(100, 'XYZ')).toBe('100.00');
  });
});

describe('formatChange', () => {
  it('adds + prefix for positive', () => {
    expect(formatChange(5.5)).toBe('+5.50');
  });
  it('keeps - prefix for negative', () => {
    expect(formatChange(-3.2)).toBe('-3.20');
  });
});

describe('formatChangePct', () => {
  it('formats change percentage with sign', () => {
    expect(formatChangePct(2.5)).toBe('+2.50%');
    expect(formatChangePct(-1.3)).toBe('-1.30%');
  });
});
