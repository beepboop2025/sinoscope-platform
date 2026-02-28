import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock all dependencies before importing
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

import { fetchFinnhubNews, fetchRSSNews } from './newsApi';
import { fetchWithTimeout } from '../../utils/helpers';
import { cacheGet } from '../CacheManager';

const mockFetch = fetchWithTimeout as ReturnType<typeof vi.fn>;
const mockCacheGet = cacheGet as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('newsApi cascade', () => {
  it('returns null when all sources fail and no keys are set', async () => {
    // No env vars set, RSS also fails
    mockFetch.mockRejectedValue(new Error('network error'));
    const result = await fetchFinnhubNews('general');
    expect(result).toBeNull();
  });

  it('returns cached results when available', async () => {
    const cached = [{ id: '1', title: 'Test', source: 'Test', url: '#', time: Date.now() }];
    mockCacheGet.mockReturnValueOnce(null).mockReturnValueOnce(cached);
    const result = await fetchFinnhubNews('general');
    expect(result).toEqual(cached);
  });
});

describe('fetchRSSNews', () => {
  it('parses RSS feed items correctly', async () => {
    const rssResponse = {
      ok: true,
      json: () => Promise.resolve({
        status: 'ok',
        feed: { title: 'Yahoo Finance' },
        items: [
          { guid: 'g1', title: 'Market Update', description: '<p>Test desc</p>', link: 'https://example.com', pubDate: '2025-01-01T00:00:00Z' },
          { guid: 'g2', title: 'Stock Rally', description: 'Another desc', link: 'https://example.com/2', pubDate: '2025-01-02T00:00:00Z' },
        ],
      }),
    };
    mockFetch.mockResolvedValue(rssResponse);

    const result = await fetchRSSNews();
    expect(result).not.toBeNull();
    expect(result!.length).toBeGreaterThan(0);
    expect(result![0].title).toBeDefined();
    // HTML should be stripped from description
    expect(result![0].summary).not.toContain('<p>');
  });

  it('handles RSS feed errors gracefully', async () => {
    mockFetch.mockRejectedValue(new Error('CORS'));
    const result = await fetchRSSNews();
    expect(result).toBeNull();
  });

  it('skips feeds with non-ok status', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'error', items: [] }),
    });
    const result = await fetchRSSNews();
    expect(result).toBeNull();
  });
});
