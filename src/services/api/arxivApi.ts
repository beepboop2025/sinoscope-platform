import { getCollectorData } from '../CollectorClient';

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

export async function fetchFinancePapers(_query: string = 'quantitative finance', _maxResults: number = 20): Promise<ArxivPaper[] | null> {
  const collected = await getCollectorData('arxiv_papers');
  if (collected && (collected as ArxivPaper[]).length > 0) return collected as ArxivPaper[];
  return null;
}

export async function fetchAllFinanceResearch(): Promise<ArxivPaper[] | null> {
  return fetchFinancePapers();
}
