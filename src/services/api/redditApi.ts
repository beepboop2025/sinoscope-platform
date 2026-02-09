import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

// Reddit public JSON has informal rate limits
createRateLimiter('reddit', 10, 60000);

interface RedditPost {
  id: string;
  title: string;
  author: string;
  score: number;
  upvoteRatio: number;
  numComments: number;
  created: number;
  subreddit: string;
  flair: string;
  url: string;
  selftext: string;
  isDD: boolean;
}

interface RedditSentiment {
  bullish: number;
  bearish: number;
  neutral: number;
  bullCount: number;
  bearCount: number;
  neutralCount: number;
  total: number;
}

const FINANCE_SUBS: string[] = ['wallstreetbets', 'cryptocurrency', 'stocks', 'investing', 'CryptoMarkets'];

export async function fetchSubredditHot(subreddit: string, limit: number = 15): Promise<RedditPost[] | null> {
  const cacheKey = `reddit_${subreddit}_hot`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as RedditPost[];

  if (!canRequest('reddit')) return null;
  consumeToken('reddit');

  try {
    const res = await fetchWithTimeout(`https://www.reddit.com/r/${subreddit}/hot.json?limit=${limit}&raw_json=1`, {
      headers: { 'User-Agent': 'DragonScope/1.0' },
    });
    if (!res.ok) throw new Error(`Reddit ${subreddit}: ${res.status}`);
    const data = await res.json() as { data?: { children?: { data: Record<string, unknown> }[] } };

    const posts: RedditPost[] = (data.data?.children || [])
      .filter((p: { data: Record<string, unknown> }) => !p.data.stickied)
      .map((p: { data: Record<string, unknown> }): RedditPost => ({
        id: p.data.id as string,
        title: p.data.title as string,
        author: p.data.author as string,
        score: p.data.score as number,
        upvoteRatio: p.data.upvote_ratio as number,
        numComments: p.data.num_comments as number,
        created: (p.data.created_utc as number) * 1000,
        subreddit: p.data.subreddit as string,
        flair: (p.data.link_flair_text || '') as string,
        url: `https://reddit.com${p.data.permalink as string}`,
        selftext: ((p.data.selftext || '') as string).slice(0, 150),
        isDD: ((p.data.link_flair_text || '') as string).toLowerCase().includes('dd'),
      }));

    cacheSet(cacheKey, posts, 180000); // 3 min cache
    return posts;
  } catch (err) {
    console.warn('[RedditAPI]', subreddit, (err as Error).message);
    return null;
  }
}

export async function fetchAllFinanceSubs(): Promise<RedditPost[] | null> {
  // Collector-first: pre-fetched reddit posts
  const collected = await getCollectorData('reddit_posts');
  if (collected && (collected as RedditPost[]).length > 0) return collected as RedditPost[];

  const cacheKey = 'reddit_finance_all';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as RedditPost[];

  const allPosts: RedditPost[] = [];
  for (const sub of FINANCE_SUBS) {
    const posts = await fetchSubredditHot(sub, 10);
    if (posts) allPosts.push(...posts);
    await new Promise<void>(r => setTimeout(r, 1000)); // Be nice to Reddit
  }

  // Sort by score
  allPosts.sort((a, b) => b.score - a.score);
  const top: RedditPost[] = allPosts.slice(0, 50);

  if (top.length > 0) {
    cacheSet(cacheKey, top, 300000);
  }
  return top.length > 0 ? top : null;
}

// Sentiment analysis from post titles (simple keyword-based)
export function analyzeSentiment(posts: RedditPost[]): RedditSentiment {
  const bullish: string[] = ['moon', 'bull', 'calls', 'buy', 'long', 'pump', 'rocket', 'gain', 'green', 'breakout', 'ath', 'yolo', 'tendies'];
  const bearish: string[] = ['bear', 'puts', 'sell', 'short', 'dump', 'crash', 'red', 'loss', 'dip', 'down', 'fear', 'recession', 'bag'];

  let bullCount: number = 0, bearCount: number = 0, neutral: number = 0;

  for (const p of posts) {
    const text: string = (p.title + ' ' + p.flair).toLowerCase();
    const isBull: boolean = bullish.some(w => text.includes(w));
    const isBear: boolean = bearish.some(w => text.includes(w));
    if (isBull && !isBear) bullCount++;
    else if (isBear && !isBull) bearCount++;
    else neutral++;
  }

  const total: number = posts.length || 1;
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

export function getMockRedditPosts(): RedditPost[] {
  return [
    { id: '1', title: 'NVDA earnings absolutely crushed it', author: 'tendies4ever', score: 15200, upvoteRatio: 0.95, numComments: 2100, created: Date.now() - 3600000, subreddit: 'wallstreetbets', flair: 'Gain', url: '', selftext: '', isDD: false },
    { id: '2', title: 'BTC about to break $70k resistance', author: 'crypto_whale', score: 8400, upvoteRatio: 0.88, numComments: 890, created: Date.now() - 7200000, subreddit: 'cryptocurrency', flair: 'ANALYSIS', url: '', selftext: '', isDD: false },
    { id: '3', title: 'Fed rate decision analysis - what to expect', author: 'dd_analyst', score: 6200, upvoteRatio: 0.92, numComments: 450, created: Date.now() - 14400000, subreddit: 'stocks', flair: 'DD', url: '', selftext: '', isDD: true },
    { id: '4', title: 'My portfolio is down 40% and I am still holding', author: 'diamond_hands', score: 12800, upvoteRatio: 0.78, numComments: 3200, created: Date.now() - 21600000, subreddit: 'wallstreetbets', flair: 'Loss', url: '', selftext: '', isDD: false },
    { id: '5', title: 'ETH staking yields compared across platforms', author: 'defi_guru', score: 3100, upvoteRatio: 0.94, numComments: 280, created: Date.now() - 28800000, subreddit: 'cryptocurrency', flair: 'GENERAL-NEWS', url: '', selftext: '', isDD: false },
    { id: '6', title: 'SPY puts printing - recession incoming?', author: 'bear_gang', score: 9500, upvoteRatio: 0.72, numComments: 1800, created: Date.now() - 36000000, subreddit: 'wallstreetbets', flair: 'YOLO', url: '', selftext: '', isDD: false },
    { id: '7', title: 'Why I am long-term bullish on MSFT', author: 'value_investor', score: 2400, upvoteRatio: 0.91, numComments: 350, created: Date.now() - 43200000, subreddit: 'investing', flair: 'DD', url: '', selftext: '', isDD: true },
    { id: '8', title: 'SOL ecosystem growing faster than expected', author: 'sol_maxi', score: 4200, upvoteRatio: 0.85, numComments: 520, created: Date.now() - 50400000, subreddit: 'CryptoMarkets', flair: '', url: '', selftext: '', isDD: false },
  ];
}
