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
  const fellBackToMock = useRef(false);
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flushTicks = useCallback((): void => {
    if (!engine) return;
    const ticks = { ...tickBuffer.current };
    tickBuffer.current = {};
    for (const tick of Object.values(ticks)) {
      engine.updateFromWS(tick as unknown as Parameters<typeof engine.updateFromWS>[0]);
    }
  }, [engine]);

  useEffect(() => {
    if (!engine) return;

    const onTick = (tick: WSTick): void => {
      tickBuffer.current[tick.symbol] = tick;
    };

    // Start flush timer for both mock and real modes
    flushTimer.current = setInterval(flushTicks, 1000);
    fellBackToMock.current = false;

    if (useMock) {
      startMockStream(onTick);
    } else {
      const pairs = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'xrpusdt', 'adausdt', 'dogeusdt', 'dotusdt'];
      subscribeBinanceTickers(pairs, onTick);

      // Auto-fallback: if no real ticks arrive within 3s, switch to mock
      fallbackTimerRef.current = setTimeout(() => {
        if (Object.keys(tickBuffer.current).length === 0 && !fellBackToMock.current) {
          console.info('[WS] No ticks received in 3s, falling back to mock stream');
          fellBackToMock.current = true;
          unsubscribeBinance();
          startMockStream(onTick);
        }
      }, 3000);
    }

    // Unified cleanup for both mock and real modes
    return () => {
      if (fallbackTimerRef.current) {
        clearTimeout(fallbackTimerRef.current);
        fallbackTimerRef.current = null;
      }
      if (flushTimer.current) {
        clearInterval(flushTimer.current);
        flushTimer.current = null;
      }

      if (useMock || fellBackToMock.current) {
        stopMockStream();
      }
      if (!useMock) {
        // Always unsubscribe Binance when we started in real mode,
        // even if we fell back to mock (idempotent call)
        unsubscribeBinance();
      }
    };
  }, [engine, useMock, flushTicks]);
}
