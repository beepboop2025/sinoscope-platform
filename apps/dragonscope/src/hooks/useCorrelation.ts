import { useState, useEffect, useRef } from 'react';
import { createCorrelationEngine } from '../engine/CorrelationEngine';
import type { MarketSnapshot } from '../types';

type CorrelationEngineInstance = ReturnType<typeof createCorrelationEngine>;

// Base prices for synthetic historical data seeding
const BASE_PRICES: Record<string, number> = {
  AAPL: 278, MSFT: 401, GOOGL: 323, NVDA: 185, AMZN: 210,
  BTC: 97000, ETH: 2700, SOL: 200,
};

// Correlation groups — assets within a group move together (positive corr)
const CORR_GROUPS: Record<string, string[]> = {
  tech: ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN'],
  crypto: ['BTC', 'ETH', 'SOL'],
};

function seedHistoricalPrices(engine: CorrelationEngineInstance, symbols: string[], points: number = 40): void {
  // Generate synthetic daily returns with realistic correlations
  const now = Date.now();
  const dayMs = 86400000;

  // Generate shared market factor per group
  const groupFactors: Record<string, number[]> = {};
  for (const [group] of Object.entries(CORR_GROUPS)) {
    groupFactors[group] = [];
    for (let i = 0; i < points; i++) {
      groupFactors[group].push((Math.random() - 0.5) * 0.02);
    }
  }

  for (const sym of symbols) {
    const base = BASE_PRICES[sym] || 100;
    let price = base * (1 + (Math.random() - 0.5) * 0.1); // Start ~5% around base

    // Find which group this symbol belongs to
    let groupKey: string | null = null;
    for (const [g, members] of Object.entries(CORR_GROUPS)) {
      if (members.includes(sym)) { groupKey = g; break; }
    }

    for (let i = 0; i < points; i++) {
      const ts = now - (points - i) * dayMs;
      // Shared factor (60% weight) + idiosyncratic (40% weight)
      const sharedReturn = groupKey ? groupFactors[groupKey][i] : 0;
      const idio = (Math.random() - 0.5) * 0.015;
      const dailyReturn = sharedReturn * 0.6 + idio * 0.4;
      price = price * (1 + dailyReturn);
      engine.addPrice(sym, price, ts);
    }
  }
}

interface CorrelationPairResult {
  symbol1: string;
  symbol2: string;
  correlation: number;
  relationship: 'positive' | 'negative';
}

interface UseCorrelationReturn {
  matrix: Record<string, Record<string, number>> | null;
  pairs: CorrelationPairResult[];
}

export function useCorrelation(marketData: MarketSnapshot | null, symbols: string[], window: number = 30): UseCorrelationReturn {
  const engineRef = useRef<CorrelationEngineInstance | null>(null);
  const seededRef = useRef<boolean>(false);
  const [matrix, setMatrix] = useState<Record<string, Record<string, number>> | null>(null);
  const [pairs, setPairs] = useState<CorrelationPairResult[]>([]);

  // Create engine and seed on first use
  if (!engineRef.current) {
    engineRef.current = createCorrelationEngine();
  }

  useEffect(() => {
    const engine = engineRef.current!;

    // Seed once with synthetic history so matrix computes immediately
    if (!seededRef.current) {
      seedHistoricalPrices(engine, symbols);
      seededRef.current = true;

      // Compute initial matrix from seed data
      const result = engine.getCorrelationMatrix(window);
      if (result?.matrix) {
        setMatrix(result.matrix);
        setPairs(engine.findHighCorrelations(0.6, window));
      }
    }

    if (!marketData) return;

    // Add live prices as they arrive
    for (const sym of symbols) {
      const data = marketData.stocks?.[sym] || marketData.crypto?.[sym] || marketData.forex?.[sym];
      if (data?.price) {
        engine.addPrice(sym, data.price);
      }
    }

    const result = engine.getCorrelationMatrix(window);
    if (result?.matrix) {
      setMatrix(result.matrix);
      setPairs(engine.findHighCorrelations(0.6, window));
    }
  }, [marketData, symbols, window]);

  return { matrix, pairs };
}
