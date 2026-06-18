import { getCollectorData } from '../CollectorClient';
import type { NewsArticle } from '../../types';

/**
 * News is now fully handled by the Celery collector which aggregates from
 * Finnhub, NewsData, NewsAPI, WorldNewsAPI, GNews, and RSS feeds server-side.
 * No more client-side cascading fallback chain or API key exposure.
 */
export async function fetchFinnhubNews(category: string = 'general'): Promise<NewsArticle[] | null> {
  const collected = await getCollectorData('news');
  if (collected && (collected as NewsArticle[]).length > 0) return collected as NewsArticle[];
  return null;
}

// Backwards-compatible aliases — all route through the collector
export const fetchNewsData = (_query?: string) => fetchFinnhubNews();
export const fetchNewsApiOrg = (_query?: string) => fetchFinnhubNews();
export const fetchWorldNewsApi = (_query?: string) => fetchFinnhubNews();
export const fetchGNews = (_query?: string) => fetchFinnhubNews();
export const fetchRSSNews = () => fetchFinnhubNews();
