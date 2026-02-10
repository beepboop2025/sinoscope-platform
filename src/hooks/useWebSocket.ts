import { useEffect, useRef, useCallback } from 'react';
import { subscribeBinanceTickers, unsubscribeBinance } from '../services/websocket/BinanceStream';
import { startMockStream, stopMockStream } from '../services/websocket/MockStream';
import type { createMarketEngine } from '../engine/MarketEngine';

type MarketEngineInstance = ReturnType<typeof createMarketEngine>;

interface WSTick {
  symbol: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
  high: number;
  low: number;
  timestamp: number;
  mock?: boolean;
}

interface UseWebSocketOptions {
  useMock?: boolean;
}

export function useWebSocket(engine: MarketEngineInstance | null, { useMock = false }: UseWebSocketOptions = {}): void {
  const tickBuffer = useRef<Record<string, WSTick>>({});
  const flushTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const flushTicks = useCallback((): void => {
    if (!engine) return;
    const ticks = { ...tickBuffer.current };
    tickBuffer.current = {};
    for (const tick of Object.values(ticks)) {
      engine.updateFromWS(tick);
    }
  }, [engine]);

  useEffect(() => {
    if (!engine) return;

    const onTick = (tick: WSTick): void => {
      tickBuffer.current[tick.symbol] = tick;
    };

    flushTimer.current = setInterval(flushTicks, 1000);

    if (useMock) {
      startMockStream(onTick);
    } else {
      const pairs = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'xrpusdt', 'adausdt', 'dogeusdt', 'dotusdt'];
      subscribeBinanceTickers(pairs, onTick);
    }

    return () => {
      clearInterval(flushTimer.current!);
      if (useMock) {
        stopMockStream();
      } else {
        unsubscribeBinance();
      }
    };
  }, [engine, useMock, flushTicks]);
}
