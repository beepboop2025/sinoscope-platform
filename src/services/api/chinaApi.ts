import { getCollectorData } from '../CollectorClient';

interface PBOCRates {
  lpr1y: number;
  lpr5y: number;
  lendingFacility: number;
  reverseRepo: number;
  rrr: number;
  lastUpdated: string;
  source: string;
}

interface CNYRates {
  cnyUsd: number;
  cnhUsd: number;
  timestamp?: number;
  isStale: boolean;
  lastUpdated?: string;
  source?: string;
}

interface ChinaEconIndicator {
  indicator: string;
  value: number;
  year: string;
  id: string;
}

interface CNYHistoryPoint {
  date: string;
  rate: number;
}

export const ChinaAPI = {
  async fetchChinaIndices(): Promise<unknown[]> {
    const collected = await getCollectorData('china_indices');
    if (collected && Array.isArray(collected) && collected.length > 0) return collected;
    return [];
  },

  async fetchChinaStocks(): Promise<unknown[]> {
    const collected = await getCollectorData('china_stocks');
    if (collected && Array.isArray(collected) && collected.length > 0) return collected;
    return [];
  },

  async fetchPBOCRates(): Promise<PBOCRates> {
    const collected = await getCollectorData('pboc_rates');
    if (collected) return collected as PBOCRates;

    // Static reference fallback — PBOC rates are not freely available via API
    return {
      lpr1y: 3.45,
      lpr5y: 3.95,
      lendingFacility: 2.50,
      reverseRepo: 1.80,
      rrr: 10.0,
      lastUpdated: '2024-02-20',
      source: 'static_reference',
    };
  },

  async fetchCNYCNHRates(): Promise<CNYRates> {
    const collected = await getCollectorData('cny_rates');
    if (collected && (collected as Record<string, unknown>).cnyUsd) {
      const collectedData = collected as Record<string, unknown>;
      const cny: number = Number(collectedData.cnyUsd) || 7.24;
      return {
        cnyUsd: cny,
        cnhUsd: collectedData.cnhUsd ? Number(collectedData.cnhUsd) : cny + 0.01,
        timestamp: (collectedData.timestamp as number) || Date.now(),
        isStale: false,
      };
    }

    // Derive from forex collector data
    const forex = await getCollectorData('forex');
    if (forex && typeof forex === 'object') {
      const rates = (forex as { rates?: Record<string, number> }).rates;
      if (rates?.CNY) {
        return { cnyUsd: rates.CNY, cnhUsd: rates.CNY + 0.01, timestamp: Date.now(), isStale: false };
      }
    }

    return { cnyUsd: 7.24, cnhUsd: 7.25, isStale: true, lastUpdated: '2024-01-01', source: 'static_fallback' };
  },

  async fetchChinaEconomic(): Promise<ChinaEconIndicator[] | null> {
    const collected = await getCollectorData('china_economic');
    if (collected && Array.isArray(collected) && collected.length > 0) return collected as ChinaEconIndicator[];
    return null;
  },

  async fetchCNYHistory(days: number = 30): Promise<CNYHistoryPoint[] | null> {
    const collected = await getCollectorData('cny_history');
    if (collected && Array.isArray(collected) && collected.length > 0) return collected as CNYHistoryPoint[];
    return null;
  },
};
