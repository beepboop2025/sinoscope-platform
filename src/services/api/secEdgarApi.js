import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';

// SEC EDGAR: 10 requests/second, we'll be conservative
createRateLimiter('sec', 10, 60000);

const EDGAR_BASE = 'https://efts.sec.gov/LATEST/search-index';
const EDGAR_FULL_TEXT = 'https://efts.sec.gov/LATEST/search';

// Fetch recent SEC filings
export async function fetchRecentFilings(query = '', forms = ['10-K', '10-Q', '8-K'], limit = 20) {
  // Collector-first: pre-fetched SEC filings
  const collected = await getCollectorData('sec_filings');
  if (collected && collected.length > 0) return collected.slice(0, limit);

  const cacheKey = `sec_filings_${query}_${forms.join('')}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('sec')) return null;
  consumeToken('sec');

  try {
    const params = new URLSearchParams({
      q: query || 'quarterly earnings',
      dateRange: 'custom',
      startdt: new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0],
      enddt: new Date().toISOString().split('T')[0],
      forms: forms.join(','),
    });

    const res = await fetch(`${EDGAR_FULL_TEXT}?${params}`, {
      headers: { 'User-Agent': 'DragonScope research@example.com' },
    });
    if (!res.ok) throw new Error(`SEC EDGAR: ${res.status}`);
    const data = await res.json();

    const filings = (data.hits?.hits || []).slice(0, limit).map(h => {
      const s = h._source || {};
      return {
        id: h._id,
        company: s.display_names?.[0] || s.entity_name || 'Unknown',
        ticker: s.tickers?.[0] || '',
        form: s.form_type || '',
        filed: s.file_date || '',
        description: s.display_description || s.file_description || '',
        url: s.file_url ? `https://www.sec.gov/Archives/${s.file_url}` : '',
      };
    });

    cacheSet(cacheKey, filings, 600000); // 10 min
    return filings;
  } catch (err) {
    console.warn('[SEC EDGAR]', err.message);
    return null;
  }
}

// Fetch filings for a specific company
export async function fetchCompanyFilings(ticker) {
  const cacheKey = `sec_company_${ticker}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('sec')) return null;
  consumeToken('sec');

  try {
    const res = await fetch(`${EDGAR_FULL_TEXT}?q=%22${ticker}%22&forms=10-K,10-Q,8-K&dateRange=custom&startdt=${new Date(Date.now() - 365 * 86400000).toISOString().split('T')[0]}&enddt=${new Date().toISOString().split('T')[0]}`, {
      headers: { 'User-Agent': 'DragonScope research@example.com' },
    });
    if (!res.ok) throw new Error(`SEC EDGAR company: ${res.status}`);
    const data = await res.json();

    const filings = (data.hits?.hits || []).slice(0, 10).map(h => {
      const s = h._source || {};
      return {
        id: h._id,
        company: s.display_names?.[0] || '',
        ticker: ticker,
        form: s.form_type || '',
        filed: s.file_date || '',
        description: s.display_description || '',
        url: s.file_url ? `https://www.sec.gov/Archives/${s.file_url}` : '',
      };
    });

    cacheSet(cacheKey, filings, 600000);
    return filings;
  } catch (err) {
    console.warn('[SEC EDGAR company]', err.message);
    return null;
  }
}

export function getMockFilings() {
  return [
    { id: '1', company: 'Apple Inc.', ticker: 'AAPL', form: '10-Q', filed: '2024-11-01', description: 'Quarterly report for Q4 2024', url: '' },
    { id: '2', company: 'Microsoft Corporation', ticker: 'MSFT', form: '10-Q', filed: '2024-10-30', description: 'Quarterly report for fiscal Q1 2025', url: '' },
    { id: '3', company: 'NVIDIA Corporation', ticker: 'NVDA', form: '10-K', filed: '2024-10-28', description: 'Annual report for fiscal year 2024', url: '' },
    { id: '4', company: 'Tesla, Inc.', ticker: 'TSLA', form: '8-K', filed: '2024-10-25', description: 'Current report - quarterly earnings', url: '' },
    { id: '5', company: 'Amazon.com, Inc.', ticker: 'AMZN', form: '10-Q', filed: '2024-10-31', description: 'Quarterly report for Q3 2024', url: '' },
    { id: '6', company: 'Alphabet Inc.', ticker: 'GOOGL', form: '10-Q', filed: '2024-10-29', description: 'Quarterly report for Q3 2024', url: '' },
    { id: '7', company: 'Meta Platforms, Inc.', ticker: 'META', form: '8-K', filed: '2024-10-30', description: 'Current report - earnings release', url: '' },
    { id: '8', company: 'JPMorgan Chase & Co.', ticker: 'JPM', form: '10-Q', filed: '2024-11-05', description: 'Quarterly report for Q3 2024', url: '' },
  ];
}
