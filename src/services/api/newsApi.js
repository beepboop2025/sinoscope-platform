import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';

const FINNHUB_KEY = () => import.meta.env.VITE_FINNHUB_API_KEY || '';
const GNEWS_KEY = () => import.meta.env.VITE_GNEWS_API_KEY || '';

const NEWS_RSS_FEEDS = [
  'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US',
  'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US',
];

export async function fetchFinnhubNews(category = 'general') {
  const key = FINNHUB_KEY();
  if (!key) {
    // Fallback to RSS feeds
    return fetchRSSNews();
  }

  const cacheKey = `news_finnhub_${category}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetch(API.FINNHUB.news(category, key));
    if (!res.ok) throw new Error(`Finnhub news: ${res.status}`);
    const data = await res.json();
    const articles = (data || []).slice(0, 20).map(a => ({
      id: a.id,
      title: a.headline,
      summary: a.summary,
      source: a.source,
      url: a.url,
      image: a.image,
      time: a.datetime * 1000,
      category: a.category,
      related: a.related,
    }));
    cacheSet(cacheKey, articles, 120000);
    return articles;
  } catch (err) {
    console.warn('[NewsAPI finnhub]', err.message);
    return fetchRSSNews();
  }
}

export async function fetchRSSNews() {
  const cacheKey = 'news_rss';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  const allArticles = [];

  for (const feedUrl of NEWS_RSS_FEEDS) {
    try {
      const res = await fetch(API.RSS2JSON.convert(feedUrl));
      if (!res.ok) continue;
      const data = await res.json();
      if (data.status !== 'ok') continue;

      const articles = (data.items || []).map(item => ({
        id: item.guid || item.link,
        title: item.title,
        summary: item.description?.replace(/<[^>]+>/g, '')?.slice(0, 200) || '',
        source: data.feed?.title || 'Yahoo Finance',
        url: item.link,
        image: item.thumbnail || item.enclosure?.link || '',
        time: new Date(item.pubDate).getTime(),
        category: 'markets',
      }));
      allArticles.push(...articles);
    } catch (err) {
      console.warn('[NewsAPI RSS]', err.message);
    }
  }

  // Sort by time, dedupe, take top 20
  const seen = new Set();
  const unique = allArticles
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

export async function fetchGNews(query = 'financial markets') {
  const key = GNEWS_KEY();
  if (!key) return null;

  const cacheKey = `news_gnews_${query}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('gnews')) return null;
  consumeToken('gnews');

  try {
    const res = await fetch(API.GNEWS.search(query, key));
    if (!res.ok) throw new Error(`GNews: ${res.status}`);
    const data = await res.json();
    const articles = (data.articles || []).map(a => ({
      id: a.url,
      title: a.title,
      summary: a.description,
      source: a.source?.name,
      url: a.url,
      image: a.image,
      time: new Date(a.publishedAt).getTime(),
      category: 'general',
    }));
    cacheSet(cacheKey, articles, 300000);
    return articles;
  } catch (err) {
    console.warn('[NewsAPI gnews]', err.message);
    return null;
  }
}
