import { useState, useEffect, useRef, useCallback } from 'react';
import { createTechnicalEngine } from '../engine/TechnicalEngine';
import type { MarketSnapshot } from '../types';

type TechnicalEngineInstance = ReturnType<typeof createTechnicalEngine>;
type IndicatorResult = NonNullable<ReturnType<TechnicalEngineInstance['getIndicators']>>;
type TechSignal = ReturnType<TechnicalEngineInstance['getSignals']>[number];
type TrendResult = ReturnType<TechnicalEngineInstance['getTrend']>;

interface UseTechnicalsReturn {
  indicators: Record<string, IndicatorResult>;
  signals: Record<string, TechSignal[]>;
  getIndicators: (symbol: string) => IndicatorResult | null;
  getSignals: (symbol: string) => TechSignal[];
  getTrend: (symbol: string) => TrendResult;
}

export function useTechnicals(marketData: MarketSnapshot | null): UseTechnicalsReturn {
  const engineRef = useRef<TechnicalEngineInstance | null>(null);
  const [indicators, setIndicators] = useState<Record<string, IndicatorResult>>({});
  const [signals, setSignals] = useState<Record<string, TechSignal[]>>({});

  if (!engineRef.current) {
    engineRef.current = createTechnicalEngine();
  }

  // Feed market data as candles into TechnicalEngine
  useEffect(() => {
    if (!marketData) return;
    const engine = engineRef.current!;
    const newIndicators: Record<string, IndicatorResult> = {};
    const newSignals: Record<string, TechSignal[]> = {};

    // Feed stock data
    for (const [sym, d] of Object.entries(marketData.stocks || {})) {
      const price = Number(d?.price) || 0;
      if (!price) continue;
      engine.addCandle(sym, {
        open: price, high: price * 1.001, low: price * 0.999,
        close: price, volume: d.volume || 0, timestamp: Date.now(),
      });
      const ind = engine.getIndicators(sym);
      if (ind) newIndicators[sym] = ind;
      const sig = engine.getSignals(sym);
      if (sig && sig.length > 0) newSignals[sym] = sig;
    }

    // Feed crypto data
    for (const [sym, d] of Object.entries(marketData.crypto || {})) {
      const price = Number(d?.price) || 0;
      if (!price) continue;
      const cleanSym = sym.replace('USDT', '');
      engine.addCandle(cleanSym, {
        open: price, high: price * 1.002, low: price * 0.998,
        close: price, volume: d.volume || 0, timestamp: Date.now(),
      });
      const ind = engine.getIndicators(cleanSym);
      if (ind) newIndicators[cleanSym] = ind;
      const sig = engine.getSignals(cleanSym);
      if (sig && sig.length > 0) newSignals[cleanSym] = sig;
    }

    if (Object.keys(newIndicators).length > 0) setIndicators(newIndicators);
    if (Object.keys(newSignals).length > 0) setSignals(newSignals);
  }, [marketData]);

  const getIndicators = useCallback((symbol: string): IndicatorResult | null => {
    return engineRef.current!.getIndicators(symbol);
  }, []);

  const getSignals = useCallback((symbol: string): TechSignal[] => {
    return engineRef.current!.getSignals(symbol);
  }, []);

  const getTrend = useCallback((symbol: string): TrendResult => {
    return engineRef.current!.getTrend(symbol);
  }, []);

  return { indicators, signals, getIndicators, getSignals, getTrend };
}
