import { useEffect, useRef, useCallback } from 'react';
import { subscribeBinanceTickers, unsubscribeBinance } from '../services/websocket/BinanceStream';
import { startMockStream, stopMockStream } from '../services/websocket/MockStream';

export function useWebSocket(engine, { useMock = false } = {}) {
  const tickBuffer = useRef({});
  const flushTimer = useRef(null);

  const flushTicks = useCallback(() => {
    if (!engine) return;
    const ticks = { ...tickBuffer.current };
    tickBuffer.current = {};
    for (const tick of Object.values(ticks)) {
      engine.updateFromWS(tick);
    }
  }, [engine]);

  useEffect(() => {
    if (!engine) return;

    const onTick = (tick) => {
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
      clearInterval(flushTimer.current);
      if (useMock) {
        stopMockStream();
      } else {
        unsubscribeBinance();
      }
    };
  }, [engine, useMock, flushTicks]);
}
