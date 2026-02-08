import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';

const FINNHUB_KEY = () => import.meta.env.VITE_FINNHUB_API_KEY || '';
const GNEWS_KEY = () => import.meta.env.VITE_GNEWS_API_KEY || '';
const NEWSDATA_KEY = () => import.meta.env.VITE_NEWSDATA_API_KEY || '';
const NEWSAPI_KEY = () => import.meta.env.VITE_NEWSAPI_API_KEY || '';
const WORLD_NEWS_KEY = () => import.meta.env.VITE_WORLD_NEWS_API_KEY || '';

const NEWS_RSS_FEEDS = [
  'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US',
  'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US',
];

/**
 * Primary entry point — cascading fallback chain:
 * Finnhub -> NewsData.io -> NewsAPI.org -> WorldNewsAPI -> GNews -> RSS
 */
export async function fetchFinnhubNews(category = 'general') {
  const cacheKey = `news_cascade_${category}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

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

async function _fetchFinnhub(category) {
  const key = FINNHUB_KEY();
  if (!key) return null;

  if (!canRequest('finnhub')) return null;
  consumeToken('finnhub');

  try {
    const res = await fetch(API.FINNHUB.news(category, key));
    if (!res.ok) return null;
    const data = await res.json();
    return (data || []).slice(0, 20).map(a => ({
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
  } catch (err) {
    console.warn('[NewsAPI finnhub]', err.message);
    return null;
  }
}

export async function fetchNewsData(query = 'finance') {
  const key = NEWSDATA_KEY();
  if (!key) return null;

  const cacheKey = `news_newsdata_${query}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('newsdata')) return null;
  consumeToken('newsdata');

  try {
    const url = query
      ? API.NEWSDATA.latest(key, query)
      : API.NEWSDATA.headlines(key);
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    if (data.status !== 'success') return null;

    const articles = (data.results || []).slice(0, 20).map(a => ({
      id: a.article_id || a.link,
      title: a.title,
      summary: a.description?.slice(0, 200) || '',
      source: a.source_name || a.source_id || 'NewsData',
      url: a.link,
      image: a.image_url || '',
      time: a.pubDate ? new Date(a.pubDate).getTime() : Date.now(),
      category: (a.category || ['business'])[0],
    }));

    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI newsdata]', err.message);
    return null;
  }
}

export async function fetchNewsApiOrg(query) {
  const key = NEWSAPI_KEY();
  if (!key) return null;

  const cacheKey = `news_newsapiorg_${query || 'headlines'}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('newsapiorg')) return null;
  consumeToken('newsapiorg');

  try {
    const url = query
      ? API.NEWSAPI_ORG.search(key, query)
      : API.NEWSAPI_ORG.headlines(key);
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    if (data.status !== 'ok') return null;

    const articles = (data.articles || []).slice(0, 20).map(a => ({
      id: a.url,
      title: a.title,
      summary: a.description || '',
      source: a.source?.name || 'NewsAPI',
      url: a.url,
      image: a.urlToImage || '',
      time: a.publishedAt ? new Date(a.publishedAt).getTime() : Date.now(),
      category: 'business',
    }));

    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI newsapi.org]', err.message);
    return null;
  }
}

export async function fetchWorldNewsApi(query = 'finance') {
  const key = WORLD_NEWS_KEY();
  if (!key) return null;

  const cacheKey = `news_worldnews_${query}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('worldnews')) return null;
  consumeToken('worldnews');

  try {
    const url = API.WORLD_NEWS_API.search(key, query);
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();

    const articles = (data.news || []).slice(0, 20).map(a => ({
      id: String(a.id || a.url),
      title: a.title,
      summary: a.text?.slice(0, 200) || '',
      source: a.source_country || 'WorldNews',
      url: a.url,
      image: a.image || '',
      time: a.publish_date ? new Date(a.publish_date).getTime() : Date.now(),
      category: 'business',
      sentiment: a.sentiment,
    }));

    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI worldnews]', err.message);
    return null;
  }
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
    if (!res.ok) return null;
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
    if (articles.length > 0) cacheSet(cacheKey, articles, 300000);
    return articles.length > 0 ? articles : null;
  } catch (err) {
    console.warn('[NewsAPI gnews]', err.message);
    return null;
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
