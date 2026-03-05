import { useState, useEffect } from 'react';
import type { createMarketEngine } from '../engine/MarketEngine';
import type { MarketSnapshot } from '../types/market';

type MarketEngineInstance = ReturnType<typeof createMarketEngine>;

export function useMarketData(engine: MarketEngineInstance | null): MarketSnapshot | null {
  const [data, setData] = useState<MarketSnapshot | null>(null);

  useEffect(() => {
    if (!engine) return;

    const unsub = engine.subscribe((snapshot) => {
      setData(snapshot as unknown as MarketSnapshot);
    });

    setData(engine.getSnapshot() as unknown as MarketSnapshot);

    return unsub;
  }, [engine]);

  return data;
}
