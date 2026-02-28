import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../CacheManager', () => ({
  cacheGet: vi.fn(() => null),
  cacheSet: vi.fn(),
}));

vi.mock('../RateLimiter', () => ({
  canRequest: vi.fn(() => true),
  consumeToken: vi.fn(),
}));

vi.mock('../CollectorClient', () => ({
  getCollectorData: vi.fn(() => null),
}));

vi.mock('../../utils/helpers', () => ({
  fetchWithTimeout: vi.fn(),
}));

import { fetchTreasuryYield, fetchYieldCurve } from './bondApi';
import { fetchWithTimeout } from '../../utils/helpers';
import { cacheGet } from '../CacheManager';

const mockFetch = fetchWithTimeout as ReturnType<typeof vi.fn>;
const mockCacheGet = cacheGet as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  // Reset env
  vi.stubEnv('VITE_FRED_API_KEY', '');
});

describe('fetchTreasuryYield', () => {
  it('returns null when no FRED key is set', async () => {
    const result = await fetchTreasuryYield('10Y');
    expect(result).toBeNull();
  });

  it('returns null for invalid maturity', async () => {
    vi.stubEnv('VITE_FRED_API_KEY', 'test-key');
    const result = await fetchTreasuryYield('99Y');
    expect(result).toBeNull();
  });

  it('parses FRED observations correctly', async () => {
    vi.stubEnv('VITE_FRED_API_KEY', 'test-key');
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        observations: [
          { date: '2025-01-15', value: '4.25' },
          { date: '2025-01-14', value: '4.20' },
          { date: '2025-01-13', value: '.' }, // FRED uses '.' for missing data
        ],
      }),
    });

    const result = await fetchTreasuryYield('10Y');
    expect(result).not.toBeNull();
    expect(result!).toHaveLength(2); // '.' entry should be filtered out
    expect(result![0].value).toBe(4.25);
    expect(result![0].date).toBe('2025-01-15');
  });

  it('handles FRED API errors gracefully', async () => {
    vi.stubEnv('VITE_FRED_API_KEY', 'test-key');
    mockFetch.mockResolvedValue({ ok: false, status: 429 });

    const result = await fetchTreasuryYield('10Y');
    expect(result).toBeNull();
  });

  it('returns cached data when available', async () => {
    const cached = [{ date: '2025-01-15', value: 4.25 }];
    vi.stubEnv('VITE_FRED_API_KEY', 'test-key');
    mockCacheGet.mockReturnValueOnce(cached);

    const result = await fetchTreasuryYield('10Y');
    expect(result).toEqual(cached);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe('fetchYieldCurve', () => {
  it('returns null when no FRED key is set', async () => {
    const result = await fetchYieldCurve();
    expect(result).toBeNull();
  });
});
