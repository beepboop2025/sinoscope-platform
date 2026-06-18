import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../CollectorClient', () => ({
  getCollectorData: vi.fn(() => null),
}));

import { fetchFinnhubNews, fetchRSSNews } from './newsApi';
import { getCollectorData } from '../CollectorClient';

const mockGetCollector = getCollectorData as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('newsApi', () => {
  it('returns null when collector has no news data', async () => {
    mockGetCollector.mockResolvedValue(null);
    const result = await fetchFinnhubNews('general');
    expect(result).toBeNull();
  });

  it('returns cached results when available from collector', async () => {
    const articles = [{ id: '1', title: 'Test', source: 'Test', url: '#', time: Date.now() }];
    mockGetCollector.mockResolvedValue(articles);
    const result = await fetchFinnhubNews('general');
    expect(result).toEqual(articles);
  });

  it('returns null for empty array from collector', async () => {
    mockGetCollector.mockResolvedValue([]);
    const result = await fetchFinnhubNews();
    expect(result).toBeNull();
  });
});

describe('fetchRSSNews', () => {
  it('delegates to collector (backwards-compatible alias)', async () => {
    const articles = [{ id: '1', title: 'RSS Item', source: 'Yahoo', url: '#', time: Date.now() }];
    mockGetCollector.mockResolvedValue(articles);
    const result = await fetchRSSNews();
    expect(result).toEqual(articles);
    expect(mockGetCollector).toHaveBeenCalledWith('news');
  });

  it('returns null when collector fails', async () => {
    mockGetCollector.mockResolvedValue(null);
    const result = await fetchRSSNews();
    expect(result).toBeNull();
  });
});
