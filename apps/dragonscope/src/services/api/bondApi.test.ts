import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../CollectorClient', () => ({
  getCollectorData: vi.fn(() => null),
}));

vi.mock('../BackendProxyClient', () => ({
  getYield: vi.fn(() => null),
}));

import { fetchTreasuryYield, fetchYieldCurve } from './bondApi';
import { getCollectorData } from '../CollectorClient';
import { getYield } from '../BackendProxyClient';

const mockGetCollector = getCollectorData as ReturnType<typeof vi.fn>;
const mockGetYield = getYield as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('fetchTreasuryYield', () => {
  it('returns collected data when available', async () => {
    const data = { '10Y': [{ date: '2025-01-15', value: 4.25 }] };
    mockGetCollector.mockResolvedValue(data);

    const result = await fetchTreasuryYield('10Y');
    expect(result).toEqual([{ date: '2025-01-15', value: 4.25 }]);
  });

  it('returns null when collector has no data and proxy fails', async () => {
    mockGetCollector.mockResolvedValue(null);
    mockGetYield.mockResolvedValue(null);

    const result = await fetchTreasuryYield('10Y');
    expect(result).toBeNull();
  });

  it('parses proxy observations and filters missing values', async () => {
    mockGetCollector.mockResolvedValue(null);
    mockGetYield.mockResolvedValue([
      { date: '2025-01-15', value: '4.25' },
      { date: '2025-01-14', value: '4.20' },
      { date: '2025-01-13', value: '.' },
    ]);

    const result = await fetchTreasuryYield('10Y');
    expect(result).not.toBeNull();
    expect(result!).toHaveLength(2);
    expect(result![0].value).toBe(4.25);
    expect(result![0].date).toBe('2025-01-15');
  });

  it('falls through to proxy when collector returns empty object', async () => {
    mockGetCollector.mockResolvedValue({});
    mockGetYield.mockResolvedValue(null);
    const result = await fetchTreasuryYield('10Y');
    expect(result).toBeNull();
    expect(mockGetYield).toHaveBeenCalled();
  });
});

describe('fetchYieldCurve', () => {
  it('returns collected yield curve when available', async () => {
    const curve = [{ maturity: '10Y', yield: 4.25, date: '2025-01-15' }];
    mockGetCollector.mockResolvedValue(curve);

    const result = await fetchYieldCurve();
    expect(result).toEqual(curve);
  });
});
