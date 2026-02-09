import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

createRateLimiter('huggingface', 30, 60000);

const FINANCE_SEARCHES = [
  'financial-sentiment',
  'stock-prediction',
  'finance-text-classification',
  'market-analysis',
  'trading',
];

export async function fetchHuggingFaceModels(search = 'finance') {
  const cacheKey = `hf_models_${search}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('huggingface')) return null;
  consumeToken('huggingface');

  try {
    const res = await fetchWithTimeout(
      `https://huggingface.co/api/models?search=${encodeURIComponent(search)}&sort=downloads&direction=-1&limit=20`
    );
    if (!res.ok) throw new Error(`HuggingFace: ${res.status}`);
    const data = await res.json();

    const models = (data || []).map(m => ({
      id: m.modelId || m.id,
      name: m.modelId || m.id,
      pipeline: m.pipeline_tag || 'unknown',
      downloads: m.downloads || 0,
      likes: m.likes || 0,
      tags: (m.tags || []).slice(0, 8),
      lastModified: m.lastModified,
      library: m.library_name || '',
      isPrivate: m.private || false,
    }));

    cacheSet(cacheKey, models, 300000); // 5 min cache
    return models;
  } catch (err) {
    console.warn('[HuggingFaceAPI]', err.message);
    return null;
  }
}

export async function fetchFinanceModels() {
  // Collector-first: pre-fetched HuggingFace models
  const collected = await getCollectorData('huggingface_models');
  if (collected && collected.length > 0) return collected;

  const cacheKey = 'hf_finance_all';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  const allModels = [];
  const seen = new Set();

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
    await new Promise(r => setTimeout(r, 300));
  }

  allModels.sort((a, b) => b.downloads - a.downloads);
  const top = allModels.slice(0, 40);

  if (top.length > 0) {
    cacheSet(cacheKey, top, 600000);
  }
  return top.length > 0 ? top : null;
}

export function getMockHuggingFaceModels() {
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
