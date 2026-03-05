import { getCollectorData } from '../CollectorClient';

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

export async function fetchGithubTrending(query: string = 'finance trading stock market crypto'): Promise<GithubRepo[] | null> {
  const collected = await getCollectorData('github_repos');
  if (collected && (collected as GithubRepo[]).length > 0) return collected as GithubRepo[];
  return null;
}

export async function fetchGithubFinanceRepos(): Promise<GithubRepo[] | null> {
  const collected = await getCollectorData('github_repos');
  if (collected && (collected as GithubRepo[]).length > 0) return collected as GithubRepo[];
  return null;
}
