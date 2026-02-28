import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

// GitHub API has 60 req/hour unauthenticated
createRateLimiter('github', 30, 3600000);

interface GithubRepo {
  id: number;
  name: string;
  description: string;
  stars: number;
  forks: number;
  language: string;
  topics: string[];
  url: string;
  updated: string;
  openIssues: number;
  license: string;
}

const FINANCE_QUERIES: string[] = [
  'topic:finance topic:trading',
  'topic:cryptocurrency topic:trading-bot',
  'topic:quantitative-finance',
  'topic:stock-market topic:python',
  'topic:algorithmic-trading',
];

export async function fetchGithubTrending(query: string = 'finance trading stock market crypto'): Promise<GithubRepo[] | null> {
  const cacheKey = `github_trending_${query}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as GithubRepo[];

  if (!canRequest('github')) return null;
  consumeToken('github');

  try {
    const q: string = encodeURIComponent(query);
    const res = await fetchWithTimeout(
      `https://api.github.com/search/repositories?q=${q}&sort=stars&order=desc&per_page=30`,
      { headers: { Accept: 'application/vnd.github.v3+json' } }
    );
    if (!res.ok) throw new Error(`GitHub: ${res.status}`);
    const data = await res.json() as { items?: Record<string, unknown>[] };

    const repos: GithubRepo[] = (data.items || []).map((r: Record<string, unknown>): GithubRepo => ({
      id: r.id as number,
      name: r.full_name as string,
      description: (r.description as string)?.slice(0, 200) || '',
      stars: r.stargazers_count as number,
      forks: r.forks_count as number,
      language: (r.language || 'Unknown') as string,
      topics: ((r.topics || []) as string[]).slice(0, 5),
      url: r.html_url as string,
      updated: r.updated_at as string,
      openIssues: r.open_issues_count as number,
      license: (r.license as { spdx_id?: string })?.spdx_id || '',
    }));

    cacheSet(cacheKey, repos, 300000); // 5 min cache
    return repos;
  } catch (err) {
    console.warn('[GitHubAPI]', (err as Error).message);
    return null;
  }
}

export async function fetchGithubFinanceRepos(): Promise<GithubRepo[] | null> {
  // Collector-first: pre-fetched github repos
  const collected = await getCollectorData('github_repos');
  if (collected && (collected as GithubRepo[]).length > 0) return collected as GithubRepo[];

  const cacheKey = 'github_finance_all';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as GithubRepo[];

  // Try multiple queries and merge
  const allRepos: GithubRepo[] = [];
  const seen = new Set<number>();

  for (const q of FINANCE_QUERIES) {
    const repos = await fetchGithubTrending(q);
    if (repos) {
      for (const r of repos) {
        if (!seen.has(r.id)) {
          seen.add(r.id);
          allRepos.push(r);
        }
      }
    }
    // Small delay between requests
    await new Promise<void>(r => setTimeout(r, 500));
  }

  // Sort by stars
  allRepos.sort((a, b) => b.stars - a.stars);
  const top: GithubRepo[] = allRepos.slice(0, 50);

  if (top.length > 0) {
    cacheSet(cacheKey, top, 600000); // 10 min cache
  }
  return top.length > 0 ? top : null;
}

// Fallback mock data for when API is rate-limited
export function getMockGithubRepos(): GithubRepo[] {
  return [
    { id: 1, name: 'freqtrade/freqtrade', description: 'Free, open source crypto trading bot', stars: 28500, forks: 6100, language: 'Python', topics: ['trading-bot', 'cryptocurrency', 'bitcoin'], url: '', updated: new Date().toISOString(), openIssues: 120, license: 'GPL-3.0' },
    { id: 2, name: 'ccxt/ccxt', description: 'A JavaScript / TypeScript / Python / C# / PHP cryptocurrency trading API', stars: 33000, forks: 7500, language: 'JavaScript', topics: ['cryptocurrency', 'exchange', 'trading'], url: '', updated: new Date().toISOString(), openIssues: 85, license: 'MIT' },
    { id: 3, name: 'microsoft/qlib', description: 'Qlib is an AI-oriented quantitative investment platform', stars: 15500, forks: 2500, language: 'Python', topics: ['quantitative-finance', 'ai', 'stock'], url: '', updated: new Date().toISOString(), openIssues: 45, license: 'MIT' },
    { id: 4, name: 'ranaroussi/yfinance', description: 'Download market data from Yahoo! Finance API', stars: 14000, forks: 2300, language: 'Python', topics: ['finance', 'stocks', 'yahoo'], url: '', updated: new Date().toISOString(), openIssues: 200, license: 'Apache-2.0' },
    { id: 5, name: 'OpenBB-finance/OpenBB', description: 'Investment Research for Everyone, Everywhere', stars: 31000, forks: 2800, language: 'Python', topics: ['finance', 'investment', 'research'], url: '', updated: new Date().toISOString(), openIssues: 60, license: 'AGPL-3.0' },
    { id: 6, name: 'vnpy/vnpy', description: 'Python-based open source quantitative trading platform', stars: 25000, forks: 8600, language: 'Python', topics: ['quantitative-trading', 'algorithmic-trading'], url: '', updated: new Date().toISOString(), openIssues: 30, license: 'MIT' },
    { id: 7, name: 'QuantConnect/Lean', description: 'Lean Algorithmic Trading Engine', stars: 10000, forks: 3400, language: 'C#', topics: ['algorithmic-trading', 'quantitative-finance'], url: '', updated: new Date().toISOString(), openIssues: 55, license: 'Apache-2.0' },
    { id: 8, name: 'stefan-jansen/machine-learning-for-trading', description: 'Code for Machine Learning for Algorithmic Trading', stars: 13000, forks: 4200, language: 'Jupyter Notebook', topics: ['machine-learning', 'trading', 'finance'], url: '', updated: new Date().toISOString(), openIssues: 15, license: 'MIT' },
    { id: 9, name: 'tensortrade-org/tensortrade', description: 'An open source reinforcement learning framework for training trading agents', stars: 4500, forks: 1000, language: 'Python', topics: ['reinforcement-learning', 'trading', 'crypto'], url: '', updated: new Date().toISOString(), openIssues: 40, license: 'Apache-2.0' },
    { id: 10, name: 'AI4Finance-Foundation/FinRL', description: 'Deep Reinforcement Learning for Quantitative Finance', stars: 10500, forks: 2300, language: 'Python', topics: ['deep-learning', 'finance', 'rl'], url: '', updated: new Date().toISOString(), openIssues: 25, license: 'MIT' },
  ];
}
