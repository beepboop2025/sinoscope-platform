import { getCollectorData } from '../CollectorClient';

interface SECFiling {
  id: string;
  company: string;
  ticker: string;
  form: string;
  filed: string;
  description: string;
  url: string;
}

export async function fetchRecentFilings(_query: string = '', _forms: string[] = ['10-K', '10-Q', '8-K'], limit: number = 20): Promise<SECFiling[] | null> {
  const collected = await getCollectorData('sec_filings');
  if (collected && (collected as SECFiling[]).length > 0) return (collected as SECFiling[]).slice(0, limit);
  return null;
}

export async function fetchCompanyFilings(ticker: string): Promise<SECFiling[] | null> {
  const collected = await getCollectorData('sec_filings');
  if (collected && (collected as SECFiling[]).length > 0) {
    const filtered = (collected as SECFiling[]).filter(f => f.ticker?.toUpperCase() === ticker.toUpperCase());
    return filtered.length > 0 ? filtered : null;
  }
  return null;
}
