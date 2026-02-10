import { useState, useEffect, useRef, useCallback } from 'react';
import { createPatternEngine } from '../engine/PatternEngine';
import type { MarketSnapshot } from '../types';

type PatternEngineInstance = ReturnType<typeof createPatternEngine>;
type PatternEvent = ReturnType<PatternEngineInstance['getRecentEvents']>[number];

interface MarketTickLike {
  price?: number;
  rate?: number;
  volume?: number;
  avgVolume?: number;
}

interface UsePatternEngineReturn {
  events: PatternEvent[];
  getSymbolEvents: (symbol: string) => PatternEvent[];
  clear: () => void;
}

export function usePatternEngine(marketData: MarketSnapshot | null): UsePatternEngineReturn {
  const engineRef = useRef<PatternEngineInstance | null>(null);
  const prevPricesRef = useRef<Record<string, number>>({});
  const [events, setEvents] = useState<PatternEvent[]>([]);

  if (!engineRef.current) {
    engineRef.current = createPatternEngine();
  }

  // Feed market data into PatternEngine and collect anomalies
  useEffect(() => {
    if (!marketData) return;
    const engine = engineRef.current!;
    const prev = prevPricesRef.current;
    const newEvents: PatternEvent[] = [];

    // Check stocks for price anomalies
    for (const [sym, d] of Object.entries(marketData.stocks || {})) {
      const tick = d as unknown as MarketTickLike;
      const price = Number(tick?.price) || 0;
      if (!price) continue;
      if (prev[sym]) {
        const anomaly = engine.detectPriceAnomaly(sym, price, prev[sym]);
        if (anomaly) newEvents.push(anomaly);
      }
      if (tick.volume && tick.avgVolume) {
        const volAnomaly = engine.detectVolumeAnomaly(sym, tick.volume, tick.avgVolume);
        if (volAnomaly) newEvents.push(volAnomaly);
      }
      prev[sym] = price;
    }

    // Check crypto for price anomalies
    for (const [sym, d] of Object.entries(marketData.crypto || {})) {
      const tick = d as unknown as MarketTickLike;
      const price = Number(tick?.price) || 0;
      if (!price) continue;
      const key = `crypto_${sym}`;
      if (prev[key]) {
        const anomaly = engine.detectPriceAnomaly(sym.replace('USDT', ''), price, prev[key]);
        if (anomaly) newEvents.push(anomaly);
      }
      prev[key] = price;
    }

    // Check forex for price anomalies
    for (const [sym, d] of Object.entries(marketData.forex || {})) {
      const tick = d as unknown as MarketTickLike;
      const price = Number(tick?.price || tick?.rate) || 0;
      if (!price) continue;
      const key = `fx_${sym}`;
      if (prev[key]) {
        const anomaly = engine.detectPriceAnomaly(sym, price, prev[key]);
        if (anomaly) newEvents.push(anomaly);
      }
      prev[key] = price;
    }

    if (newEvents.length > 0) {
      setEvents(engine.getRecentEvents(50));
    }
    prevPricesRef.current = prev;
  }, [marketData]);

  const getSymbolEvents = useCallback((symbol: string): PatternEvent[] => {
    return engineRef.current!.getSymbolEvents(symbol);
  }, []);

  const clear = useCallback((): void => {
    engineRef.current!.clear();
    setEvents([]);
  }, []);

  return { events, getSymbolEvents, clear };
}
