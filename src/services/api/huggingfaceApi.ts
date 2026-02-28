import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

createRateLimiter('huggingface', 30, 60000);

interface HuggingFaceModel {
  id: string;
  name: string;
  pipeline: string;
  downloads: number;
  likes: number;
  tags: string[];
  lastModified: string;
  library: string;
  isPrivate?: boolean;
}

const FINANCE_SEARCHES: string[] = [
  'financial-sentiment',
  'stock-prediction',
  'finance-text-classification',
  'market-analysis',
  'trading',
];

export async function fetchHuggingFaceModels(search: string = 'finance'): Promise<HuggingFaceModel[] | null> {
  const cacheKey = `hf_models_${search}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as HuggingFaceModel[];

  if (!canRequest('huggingface')) return null;
  consumeToken('huggingface');

  try {
    const res = await fetchWithTimeout(
      `https://huggingface.co/api/models?search=${encodeURIComponent(search)}&sort=downloads&direction=-1&limit=20`
    );
    if (!res.ok) throw new Error(`HuggingFace: ${res.status}`);
    const data: unknown = await res.json();

    const models: HuggingFaceModel[] = ((data as Record<string, unknown>[]) || []).map((m: Record<string, unknown>): HuggingFaceModel => ({
      id: (m.modelId || m.id) as string,
      name: (m.modelId || m.id) as string,
      pipeline: (m.pipeline_tag || 'unknown') as string,
      downloads: (m.downloads || 0) as number,
      likes: (m.likes || 0) as number,
      tags: ((m.tags || []) as string[]).slice(0, 8),
      lastModified: m.lastModified as string,
      library: (m.library_name || '') as string,
      isPrivate: (m.private || false) as boolean,
    }));

    cacheSet(cacheKey, models, 300000); // 5 min cache
    return models;
  } catch (err) {
    console.warn('[HuggingFaceAPI]', (err as Error).message);
    return null;
  }
}

export async function fetchFinanceModels(): Promise<HuggingFaceModel[] | null> {
  // Collector-first: pre-fetched HuggingFace models
  const collected = await getCollectorData('huggingface_models');
  if (collected && (collected as HuggingFaceModel[]).length > 0) return collected as HuggingFaceModel[];

  const cacheKey = 'hf_finance_all';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as HuggingFaceModel[];

  const allModels: HuggingFaceModel[] = [];
  const seen = new Set<string>();

  for (const q of FINANCE_SEARCHES) {
    const models = await fetchHuggingFaceModels(q);
    if (models) {
      for (const m of models) {
        if (!seen.has(m.id)) {
          seen.add(m.id);
          allModels.push(m);
        }
      }
    }
    await new Promise<void>(r => setTimeout(r, 300));
  }

  allModels.sort((a, b) => b.downloads - a.downloads);
  const top: HuggingFaceModel[] = allModels.slice(0, 40);

  if (top.length > 0) {
    cacheSet(cacheKey, top, 600000);
  }
  return top.length > 0 ? top : null;
}

export function getMockHuggingFaceModels(): HuggingFaceModel[] {
  return [
    { id: 'ProsusAI/finbert', name: 'ProsusAI/finbert', pipeline: 'text-classification', downloads: 5800000, likes: 520, tags: ['finance', 'sentiment', 'bert'], lastModified: new Date().toISOString(), library: 'transformers' },
    { id: 'yiyanghkust/finbert-tone', name: 'yiyanghkust/finbert-tone', pipeline: 'text-classification', downloads: 1200000, likes: 180, tags: ['finance', 'sentiment'], lastModified: new Date().toISOString(), library: 'transformers' },
    { id: 'mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis', name: 'mrm8488/distilroberta-finetuned-financial-news', pipeline: 'text-classification', downloads: 950000, likes: 95, tags: ['finance', 'sentiment', 'roberta'], lastModified: new Date().toISOString(), library: 'transformers' },
    { id: 'nickmuchi/sec-bert-finetuned-finance-classification', name: 'nickmuchi/sec-bert-finance', pipeline: 'text-classification', downloads: 420000, likes: 45, tags: ['finance', 'sec', 'bert'], lastModified: new Date().toISOString(), library: 'transformers' },
    { id: 'Jean-Baptiste/roberta-large-financial-news-sentiment-en', name: 'Jean-Baptiste/roberta-large-financial-sentiment', pipeline: 'text-classification', downloads: 380000, likes: 60, tags: ['finance', 'sentiment', 'roberta'], lastModified: new Date().toISOString(), library: 'transformers' },
    { id: 'ahmedrachid/FinancialBERT-Sentiment-Analysis', name: 'ahmedrachid/FinancialBERT-Sentiment', pipeline: 'text-classification', downloads: 310000, likes: 42, tags: ['finance', 'sentiment', 'bert'], lastModified: new Date().toISOString(), library: 'transformers' },
    { id: 'StephanAkkworken/flair-english-financial-news-sentiment', name: 'StephanAkkworken/flair-financial-sentiment', pipeline: 'text-classification', downloads: 180000, likes: 28, tags: ['finance', 'flair', 'sentiment'], lastModified: new Date().toISOString(), library: 'flair' },
    { id: 'FinanceInc/auditor_sentiment_finetuned', name: 'FinanceInc/auditor_sentiment', pipeline: 'text-classification', downloads: 95000, likes: 18, tags: ['finance', 'auditing', 'sentiment'], lastModified: new Date().toISOString(), library: 'transformers' },
  ];
}
