import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

// arXiv API is free but has 3 sec delay requirement between requests
createRateLimiter('arxiv', 10, 60000);

interface ArxivPaper {
  id: string;
  title: string;
  summary: string;
  authors: (string | null)[];
  categories: (string | null)[];
  published: string;
  pdfUrl: string;
  url: string;
}

// Fetch recent quantitative finance papers
export async function fetchFinancePapers(query: string = 'quantitative finance', maxResults: number = 20): Promise<ArxivPaper[] | null> {
  const cacheKey = `arxiv_${query}_${maxResults}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as ArxivPaper[];

  if (!canRequest('arxiv')) return null;
  consumeToken('arxiv');

  try {
    const params = new URLSearchParams({
      search_query: `cat:q-fin* OR all:${query}`,
      start: '0',
      max_results: String(maxResults),
      sortBy: 'submittedDate',
      sortOrder: 'descending',
    });

    const res = await fetchWithTimeout(`https://export.arxiv.org/api/query?${params}`);
    if (!res.ok) throw new Error(`arXiv: ${res.status}`);
    const text: string = await res.text();

    // Parse XML (arXiv uses Atom format)
    const parser = new DOMParser();
    const xml: Document = parser.parseFromString(text, 'text/xml');
    const entries: NodeListOf<Element> = xml.querySelectorAll('entry');

    const papers: ArxivPaper[] = [];
    for (const entry of entries) {
      const title: string = entry.querySelector('title')?.textContent?.trim().replace(/\s+/g, ' ') || '';
      const summary: string = entry.querySelector('summary')?.textContent?.trim().replace(/\s+/g, ' ').slice(0, 300) || '';
      const published: string = entry.querySelector('published')?.textContent || '';
      const id: string = entry.querySelector('id')?.textContent || '';
      const authors: (string | null)[] = [...entry.querySelectorAll('author name')].map(n => n.textContent).slice(0, 3);
      const categories: (string | null)[] = [...entry.querySelectorAll('category')].map(c => c.getAttribute('term')).filter(Boolean).slice(0, 3);
      const pdfLink: string = [...entry.querySelectorAll('link')].find(l => l.getAttribute('title') === 'pdf')?.getAttribute('href') || '';

      papers.push({
        id,
        title,
        summary,
        authors,
        categories,
        published: published.split('T')[0],
        pdfUrl: pdfLink,
        url: id,
      });
    }

    cacheSet(cacheKey, papers, 600000); // 10 min
    return papers;
  } catch (err) {
    console.warn('[arXiv]', (err as Error).message);
    return null;
  }
}

// Specific finance sub-categories
export async function fetchAllFinanceResearch(): Promise<ArxivPaper[] | null> {
  // Collector-first: pre-fetched arxiv papers
  const collected = await getCollectorData('arxiv_papers');
  if (collected && (collected as ArxivPaper[]).length > 0) return collected as ArxivPaper[];

  const cacheKey = 'arxiv_finance_all';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as ArxivPaper[];

  const queries: string[] = [
    'algorithmic trading machine learning',
    'portfolio optimization deep learning',
    'financial sentiment analysis NLP',
    'cryptocurrency market prediction',
  ];

  const allPapers: ArxivPaper[] = [];
  const seen = new Set<string>();

  for (const q of queries) {
    const papers = await fetchFinancePapers(q, 10);
    if (papers) {
      for (const p of papers) {
        if (!seen.has(p.id)) {
          seen.add(p.id);
          allPapers.push(p);
        }
      }
    }
    await new Promise<void>(r => setTimeout(r, 3500)); // arXiv requires 3 sec between requests
  }

  allPapers.sort((a, b) => b.published.localeCompare(a.published));
  const top: ArxivPaper[] = allPapers.slice(0, 30);

  if (top.length > 0) {
    cacheSet(cacheKey, top, 600000);
  }
  return top.length > 0 ? top : null;
}

export function getMockPapers(): ArxivPaper[] {
  return [
    { id: '1', title: 'Deep Reinforcement Learning for Portfolio Management', summary: 'We propose a novel DRL framework for dynamic portfolio allocation that outperforms traditional mean-variance optimization...', authors: ['Zhang Y.', 'Wang L.', 'Chen H.'], categories: ['q-fin.PM', 'cs.AI'], published: '2024-11-10', pdfUrl: '', url: '' },
    { id: '2', title: 'Transformer-based Models for Stock Price Prediction', summary: 'This paper explores the application of attention mechanisms and transformer architectures for multi-step stock price forecasting...', authors: ['Liu J.', 'Kim S.'], categories: ['q-fin.ST', 'cs.LG'], published: '2024-11-08', pdfUrl: '', url: '' },
    { id: '3', title: 'Sentiment Analysis of Financial News Using Large Language Models', summary: 'We fine-tune GPT-4 and LLaMA models on financial news datasets to assess market sentiment with unprecedented accuracy...', authors: ['Smith A.', 'Brown R.', 'Davis M.'], categories: ['q-fin.GN', 'cs.CL'], published: '2024-11-06', pdfUrl: '', url: '' },
    { id: '4', title: 'Decentralized Finance Yield Optimization via Convex Programming', summary: 'We formulate DeFi yield farming as a convex optimization problem and derive optimal strategies across multiple protocols...', authors: ['Nakamoto S.', 'Buterin V.'], categories: ['q-fin.MF', 'math.OC'], published: '2024-11-04', pdfUrl: '', url: '' },
    { id: '5', title: 'Market Microstructure and High-Frequency Trading with Neural ODEs', summary: 'We model limit order book dynamics using neural ordinary differential equations, achieving state-of-the-art prediction...', authors: ['Li X.', 'Wang Q.'], categories: ['q-fin.TR', 'cs.AI'], published: '2024-11-02', pdfUrl: '', url: '' },
    { id: '6', title: 'Cryptocurrency Cross-Exchange Arbitrage Detection with Graph Neural Networks', summary: 'A novel GNN approach to detect real-time arbitrage opportunities across decentralized and centralized crypto exchanges...', authors: ['Park J.', 'Lee H.', 'Choi K.'], categories: ['q-fin.CP', 'cs.LG'], published: '2024-10-31', pdfUrl: '', url: '' },
  ];
}
