import { getCollectorData } from '../CollectorClient';

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

export async function fetchSubredditHot(_subreddit: string, _limit: number = 15): Promise<RedditPost[] | null> {
  const collected = await getCollectorData('reddit_posts');
  if (collected && (collected as RedditPost[]).length > 0) return collected as RedditPost[];
  return null;
}

export async function fetchAllFinanceSubs(): Promise<RedditPost[] | null> {
  return fetchSubredditHot('all');
}

// Pure utility — keyword-based sentiment analysis on post titles
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
