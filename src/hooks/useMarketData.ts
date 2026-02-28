import { useState, useEffect } from 'react';
import type { createMarketEngine } from '../engine/MarketEngine';

type MarketEngineInstance = ReturnType<typeof createMarketEngine>;
type MarketEngineSnapshot = Parameters<Parameters<MarketEngineInstance['subscribe']>[0]>[0];

export function useMarketData(engine: MarketEngineInstance | null): MarketEngineSnapshot | null {
  const [data, setData] = useState<MarketEngineSnapshot | null>(null);

  useEffect(() => {
    if (!engine) return;

    const unsub = engine.subscribe((snapshot) => {
      setData(snapshot);
    });

    setData(engine.getSnapshot());

    return unsub;
  }, [engine]);

  return data;
}
