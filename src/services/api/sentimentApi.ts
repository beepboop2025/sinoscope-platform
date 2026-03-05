import { getCollectorData } from '../CollectorClient';

interface FearGreedEntry {
  value: number;
  label: string;
  timestamp: number;
}

interface SectorPerformanceItem {
  name: string;
  symbol: string;
  changePct: number;
  weekPct: number;
  monthPct: number;
  price?: number;
}

export async function fetchFearGreedIndex(): Promise<FearGreedEntry[] | null> {
  const collected = await getCollectorData('fear_greed');
  if (collected && (collected as FearGreedEntry[]).length > 0) return collected as FearGreedEntry[];
  return null;
}

export async function fetchSectorPerformance(): Promise<SectorPerformanceItem[] | null> {
  const collected = await getCollectorData('sectors');
  if (collected && (collected as SectorPerformanceItem[]).length > 0) return collected as SectorPerformanceItem[];
  return null;
}
