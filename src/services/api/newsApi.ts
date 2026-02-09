import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';
import type { NewsArticle } from '../../types';

const FINNHUB_KEY = (): string => import.meta.env.VITE_FINNHUB_API_KEY || '';
const GNEWS_KEY = (): string => import.meta.env.VITE_GNEWS_API_KEY || '';
const NEWSDATA_KEY = (): string => import.meta.env.VITE_NEWSDATA_API_KEY || '';
const NEWSAPI_KEY = (): string => import.meta.env.VITE_NEWSAPI_API_KEY || '';
const WORLD_NEWS_KEY = (): string => import.meta.env.VITE_WORLD_NEWS_API_KEY || '';

const NEWS_RSS_FEEDS: string[] = [
  'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US',
  'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US',
];

/**
 * Primary entry point -- cascading fallback chain:
 * Finnhub -> NewsData.io -> NewsAPI.org -> WorldNewsAPI -> GNews -> RSS
 */
export async function fetchFinnhubNews(category: string = 'general'): Promise<NewsArticle[] | null> {
  // Collector-first: pre-fetched news
  const collected = await getCollectorData('news');
  if (collected && (collected as NewsArticle[]).length > 0) return collected as NewsArticle[];

  const cacheKey = `news_cascade_${category}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as NewsArticle[];

  // 1. Finnhub (if key available)
  const finnhubResult = await _fetchFinnhub(category);
  if (finnhubResult && finnhubResult.length > 0) {
    cacheSet(cacheKey, finnhubResult, 120000);
    return finnhubResult;
  }

  // 2. NewsData.io (free: 500 calls/month)
  const newsDataResult = await fetchNewsData('financial markets');
  if (newsDataResult && newsDataResult.length > 0) {
    cacheSet(cacheKey, newsDataResult, 120000);
    return newsDataResult;
  }

  // 3. NewsAPI.org (free: 100 calls/day)
  const newsApiResult = await fetchNewsApiOrg();
  if (newsApiResult && newsApiResult.length > 0) {
    cacheSet(cacheKey, newsApiResult, 120000);
    return newsApiResult;
  }

  // 4. WorldNewsAPI (free tier)
  const worldResult = await fetchWorldNewsApi('stock market finance');
  if (worldResult && worldResult.length > 0) {
    cacheSet(cacheKey, worldResult, 120000);
    return worldResult;
  }

  // 5. GNews (if key available)
  const gnewsResult = await fetchGNews('financial markets');
  if (gnewsResult && gnewsResult.length > 0) {
    cacheSet(cacheKey, gnewsResult, 120000);
    return gnewsResult;
  }

  // 6. RSS fallback (always works, no key needed)
  const rssResult = await fetchRSSNews();
  if (rssResult && rssResult.length > 0) {
    cacheSet(cacheKey, rssResult, 120000);
  }
  return rssResult;
}

// --- Individual API implementations ---

async function _fetchFinnhub(category: string): Promise<NewsArticle[] | null> {
  const key: string = FINNHUB_KEY();
  if (!key) return null;

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetchWithTimeout(API.FINNHUB.news(category, key));
    if (!res.ok) return null;
    const data: unknown = await res.json();
    return ((data as Record<string, unknown>[]) || []).slice(0, 20).map((a: Record<string, unknown>): NewsArticle => ({
      id: String(a.id),
      title: a.headline as string,
      summary: a.summary as string,
      source: a.source as string,
      url: a.url as string,
      image: a.image as string,
      time: (a.datetime as number) * 1000,
      category: a.category as string,
      related: a.related as string,
    }));
  } catch (err) {
    console.warn('[NewsAPI finnhub]', (err as Error).message);
    return null;
  }
}

export async function fetchNewsData(query: string = 'finance'): Promise<NewsArticle[] | null> {
  const key: string = NEWSDATA_KEY();
  if (!key) return null;

  const cacheKey = `news_newsdata_${query}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as NewsArticle[];

  if (!canRequest('newsdata')) return null;
  consumeToken('newsdata');

  try {
    const url: string = query
      ? API.NEWSDATA.latest(key, query)
      : API.NEWSDATA.headlines(key);
    const res = await fetchWithTimeout(url);
    if (!res.ok) return null;
    const data = await res.json() as { status: string; results?: Record<string, unknown>[] };
    if (data.status !== 'success') return null;

    const articles: NewsArticle[] = (data.results || []).slice(0, 20).map((a: Record<string, unknown>): NewsArticle => ({
      id: (a.article_id || a.link) as string,
      title: a.title as string,
      summary: (a.description as string)?.slice(0, 200) || '',
      source: (a.source_name || a.source_id || 'NewsData') as string,
      url: a.link as string,
      image: (a.image_url || '') as string,
      time: a.pubDate ? new Date(a.pubDate as string).getTime() : Date.now(),
      category: ((a.category as string[]) || ['business'])[0],
    }));

    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI newsdata]', (err as Error).message);
    return null;
  }
}

export async function fetchNewsApiOrg(query?: string): Promise<NewsArticle[] | null> {
  const key: string = NEWSAPI_KEY();
  if (!key) return null;

  const cacheKey = `news_newsapiorg_${query || 'headlines'}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as NewsArticle[];

  if (!canRequest('newsapiorg')) return null;
  consumeToken('newsapiorg');

  try {
    const url: string = query
      ? API.NEWSAPI_ORG.search(key, query)
      : API.NEWSAPI_ORG.headlines(key);
    const res = await fetchWithTimeout(url);
    if (!res.ok) return null;
    const data = await res.json() as { status: string; articles?: Record<string, unknown>[] };
    if (data.status !== 'ok') return null;

    const articles: NewsArticle[] = (data.articles || []).slice(0, 20).map((a: Record<string, unknown>): NewsArticle => ({
      id: a.url as string,
      title: a.title as string,
      summary: (a.description || '') as string,
      source: (a.source as { name?: string })?.name || 'NewsAPI',
      url: a.url as string,
      image: (a.urlToImage || '') as string,
      time: a.publishedAt ? new Date(a.publishedAt as string).getTime() : Date.now(),
      category: 'business',
    }));

    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI newsapi.org]', (err as Error).message);
    return null;
  }
}

export async function fetchWorldNewsApi(query: string = 'finance'): Promise<NewsArticle[] | null> {
  const key: string = WORLD_NEWS_KEY();
  if (!key) return null;

  const cacheKey = `news_worldnews_${query}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as NewsArticle[];

  if (!canRequest('worldnews')) return null;
  consumeToken('worldnews');

  try {
    const url: string = API.WORLD_NEWS_API.search(key, query);
    const res = await fetchWithTimeout(url);
    if (!res.ok) return null;
    const data = await res.json() as { news?: Record<string, unknown>[] };

    const articles: NewsArticle[] = (data.news || []).slice(0, 20).map((a: Record<string, unknown>): NewsArticle => ({
      id: String(a.id || a.url),
      title: a.title as string,
      summary: (a.text as string)?.slice(0, 200) || '',
      source: (a.source_country || 'WorldNews') as string,
      url: a.url as string,
      image: (a.image || '') as string,
      time: a.publish_date ? new Date(a.publish_date as string).getTime() : Date.now(),
      category: 'business',
      sentiment: a.sentiment as number | undefined,
    }));

    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI worldnews]', (err as Error).message);
    return null;
  }
}

export async function fetchGNews(query: string = 'financial markets'): Promise<NewsArticle[] | null> {
  const key: string = GNEWS_KEY();
  if (!key) return null;

  const cacheKey = `news_gnews_${query}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as NewsArticle[];

  if (!canRequest('gnews')) return null;
  consumeToken('gnews');

  try {
    const res = await fetchWithTimeout(API.GNEWS.search(query, key));
    if (!res.ok) return null;
    const data = await res.json() as { articles?: Record<string, unknown>[] };
    const articles: NewsArticle[] = (data.articles || []).map((a: Record<string, unknown>): NewsArticle => ({
      id: a.url as string,
      title: a.title as string,
      summary: a.description as string,
      source: (a.source as { name?: string })?.name as string,
      url: a.url as string,
      image: a.image as string,
      time: a.publishedAt ? new Date(a.publishedAt as string).getTime() : Date.now(),
      category: 'general',
    }));
    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI gnews]', (err as Error).message);
    return null;
  }
}

export async function fetchRSSNews(): Promise<NewsArticle[] | null> {
  const cacheKey = 'news_rss';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as NewsArticle[];

  const allArticles: NewsArticle[] = [];

  for (const feedUrl of NEWS_RSS_FEEDS) {
    try {
      const res = await fetchWithTimeout(API.RSS2JSON.convert(feedUrl));
      if (!res.ok) continue;
      const data = await res.json() as { status: string; feed?: { title?: string }; items?: Record<string, unknown>[] };
      if (data.status !== 'ok') continue;

      const articles: NewsArticle[] = (data.items || []).map((item: Record<string, unknown>): NewsArticle => ({
        id: (item.guid || item.link) as string,
        title: item.title as string,
        summary: (item.description as string)?.replace(/<[^>]+>/g, '')?.slice(0, 200) || '',
        source: data.feed?.title || 'Yahoo Finance',
        url: item.link as string,
        image: (item.thumbnail || (item.enclosure as { link?: string })?.link || '') as string,
        time: new Date(item.pubDate as string).getTime(),
        category: 'markets',
      }));
      allArticles.push(...articles);
    } catch (err) {
      console.warn('[NewsAPI RSS]', (err as Error).message);
    }
  }

  // Sort by time, dedupe, take top 20
  const seen = new Set<string>();
  const unique: NewsArticle[] = allArticles
    .sort((a, b) => b.time - a.time)
    .filter(a => {
      if (seen.has(a.title)) return false;
      seen.add(a.title);
      return true;
    })
    .slice(0, 20);

  if (unique.length > 0) {
    cacheSet(cacheKey, unique, 120000);
  }
  return unique.length > 0 ? unique : null;
}
