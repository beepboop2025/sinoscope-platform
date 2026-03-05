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
  [key: string]: string | number | boolean | undefined;
}

interface UseWebSocketOptions {
  useMock?: boolean;
}

export function useWebSocket(engine: MarketEngineInstance | null, { useMock = false }: UseWebSocketOptions = {}): void {
  const tickBuffer = useRef<Record<string, WSTick>>({});
  const flushTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const fellBackToMock = useRef(false);

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
    fellBackToMock.current = false;

    if (useMock) {
      startMockStream(onTick);
    } else {
      const pairs = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'xrpusdt', 'adausdt', 'dogeusdt', 'dotusdt'];
      subscribeBinanceTickers(pairs, onTick);

      // Auto-fallback: if no real ticks arrive within 3s, switch to mock
      const fallbackTimer = setTimeout(() => {
        if (Object.keys(tickBuffer.current).length === 0 && !fellBackToMock.current) {
          console.info('[WS] No ticks received in 3s, falling back to mock stream');
          fellBackToMock.current = true;
          unsubscribeBinance();
          startMockStream(onTick);
        }
      }, 3000);

      return () => {
        clearTimeout(fallbackTimer);
        clearInterval(flushTimer.current!);
        if (fellBackToMock.current) {
          stopMockStream();
        } else {
          unsubscribeBinance();
        }
      };
    }

    return () => {
      clearInterval(flushTimer.current!);
      if (useMock) {
        stopMockStream();
      }
    };
  }, [engine, useMock, flushTicks]);
}
