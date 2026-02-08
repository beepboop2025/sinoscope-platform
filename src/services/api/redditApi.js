import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';

// Reddit public JSON has informal rate limits
createRateLimiter('reddit', 10, 60000);

const FINANCE_SUBS = ['wallstreetbets', 'cryptocurrency', 'stocks', 'investing', 'CryptoMarkets'];

export async function fetchSubredditHot(subreddit, limit = 15) {
  const cacheKey = `reddit_${subreddit}_hot`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('reddit')) return null;
  consumeToken('reddit');

  try {
    const res = await fetch(`https://www.reddit.com/r/${subreddit}/hot.json?limit=${limit}&raw_json=1`, {
      headers: { 'User-Agent': 'DragonScope/1.0' },
    });
    if (!res.ok) throw new Error(`Reddit ${subreddit}: ${res.status}`);
    const data = await res.json();

    const posts = (data.data?.children || [])
      .filter(p => !p.data.stickied)
      .map(p => ({
        id: p.data.id,
        title: p.data.title,
        author: p.data.author,
        score: p.data.score,
        upvoteRatio: p.data.upvote_ratio,
        numComments: p.data.num_comments,
        created: p.data.created_utc * 1000,
        subreddit: p.data.subreddit,
        flair: p.data.link_flair_text || '',
        url: `https://reddit.com${p.data.permalink}`,
        selftext: (p.data.selftext || '').slice(0, 150),
        isDD: (p.data.link_flair_text || '').toLowerCase().includes('dd'),
      }));

    cacheSet(cacheKey, posts, 180000); // 3 min cache
    return posts;
  } catch (err) {
    console.warn('[RedditAPI]', subreddit, err.message);
    return null;
  }
}

export async function fetchAllFinanceSubs() {
  // Collector-first: pre-fetched reddit posts
  const collected = await getCollectorData('reddit_posts');
  if (collected && collected.length > 0) return collected;

  const cacheKey = 'reddit_finance_all';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  const allPosts = [];
  for (const sub of FINANCE_SUBS) {
    const posts = await fetchSubredditHot(sub, 10);
    if (posts) allPosts.push(...posts);
    await new Promise(r => setTimeout(r, 1000)); // Be nice to Reddit
  }

  // Sort by score
  allPosts.sort((a, b) => b.score - a.score);
  const top = allPosts.slice(0, 50);

  if (top.length > 0) {
    cacheSet(cacheKey, top, 300000);
  }
  return top.length > 0 ? top : null;
}

// Sentiment analysis from post titles (simple keyword-based)
export function analyzeSentiment(posts) {
  const bullish = ['moon', 'bull', 'calls', 'buy', 'long', 'pump', 'rocket', 'gain', 'green', 'breakout', 'ath', 'yolo', 'tendies'];
  const bearish = ['bear', 'puts', 'sell', 'short', 'dump', 'crash', 'red', 'loss', 'dip', 'down', 'fear', 'recession', 'bag'];

  let bullCount = 0, bearCount = 0, neutral = 0;

  for (const p of posts) {
    const text = (p.title + ' ' + p.flair).toLowerCase();
    const isBull = bullish.some(w => text.includes(w));
    const isBear = bearish.some(w => text.includes(w));
    if (isBull && !isBear) bullCount++;
    else if (isBear && !isBull) bearCount++;
    else neutral++;
  }

  const total = posts.length || 1;
  return {
    bullish: Math.round((bullCount / total) * 100),
    bearish: Math.round((bearCount / total) * 100),
    neutral: Math.round((neutral / total) * 100),
    bullCount,
    bearCount,
    neutralCount: neutral,
    total: posts.length,
  };
}

export function getMockRedditPosts() {
  return [
    { id: '1', title: 'NVDA earnings absolutely crushed it 🚀', author: 'tendies4ever', score: 15200, upvoteRatio: 0.95, numComments: 2100, created: Date.now() - 3600000, subreddit: 'wallstreetbets', flair: 'Gain', url: '', selftext: '' },
    { id: '2', title: 'BTC about to break $70k resistance', author: 'crypto_whale', score: 8400, upvoteRatio: 0.88, numComments: 890, created: Date.now() - 7200000, subreddit: 'cryptocurrency', flair: 'ANALYSIS', url: '', selftext: '' },
    { id: '3', title: 'Fed rate decision analysis - what to expect', author: 'dd_analyst', score: 6200, upvoteRatio: 0.92, numComments: 450, created: Date.now() - 14400000, subreddit: 'stocks', flair: 'DD', url: '', selftext: '' },
    { id: '4', title: 'My portfolio is down 40% and I am still holding', author: 'diamond_hands', score: 12800, upvoteRatio: 0.78, numComments: 3200, created: Date.now() - 21600000, subreddit: 'wallstreetbets', flair: 'Loss', url: '', selftext: '' },
    { id: '5', title: 'ETH staking yields compared across platforms', author: 'defi_guru', score: 3100, upvoteRatio: 0.94, numComments: 280, created: Date.now() - 28800000, subreddit: 'cryptocurrency', flair: 'GENERAL-NEWS', url: '', selftext: '' },
    { id: '6', title: 'SPY puts printing - recession incoming?', author: 'bear_gang', score: 9500, upvoteRatio: 0.72, numComments: 1800, created: Date.now() - 36000000, subreddit: 'wallstreetbets', flair: 'YOLO', url: '', selftext: '' },
    { id: '7', title: 'Why I am long-term bullish on MSFT', author: 'value_investor', score: 2400, upvoteRatio: 0.91, numComments: 350, created: Date.now() - 43200000, subreddit: 'investing', flair: 'DD', url: '', selftext: '' },
    { id: '8', title: 'SOL ecosystem growing faster than expected', author: 'sol_maxi', score: 4200, upvoteRatio: 0.85, numComments: 520, created: Date.now() - 50400000, subreddit: 'CryptoMarkets', flair: '', url: '', selftext: '' },
  ];
}
