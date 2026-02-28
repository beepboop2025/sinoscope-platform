import { useEffect, useRef } from 'react';
import type { createMarketEngine } from '../engine/MarketEngine';

type MarketEngineInstance = ReturnType<typeof createMarketEngine>;

interface BackendWSMessage {
  type: string;
  category?: string;
  data?: unknown;
}

const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000];
const SUBSCRIBE_CATEGORIES = [
  'crypto_markets', 'forex', 'stocks', 'bonds', 'commodities', 'news', 'fear_greed',
];

/**
 * Connects to the backend WebSocket at /ws/market-data.
 * Subscribes to collector categories and feeds updates into MarketEngine.
 * Coexists with Binance WS (useWebSocket) — backend WS provides multi-category
 * collector updates while Binance provides sub-second crypto tickers.
 */
export function useBackendWS(engine: MarketEngineInstance | null): void {
  const wsRef = useRef<WebSocket | null>(null);
  const intentionalClose = useRef(false);
  const retryCount = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!engine) return;

    function connect() {
      if (intentionalClose.current) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${window.location.host}/ws/market-data`;

      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        retryCount.current = 0;
        // Subscribe to all categories
        ws.send(JSON.stringify({
          type: 'subscribe',
          categories: SUBSCRIBE_CATEGORIES,
        }));
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: BackendWSMessage = JSON.parse(event.data);
          if (msg.type === 'update' && msg.category && msg.data) {
            engine.updateCategory(msg.category, msg.data);
          }
          // Heartbeat and subscribed messages are silently ignored
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (!intentionalClose.current) {
          scheduleReconnect();
        }
      };

      ws.onerror = () => {
        // onclose will fire after onerror, reconnection handled there
      };
    }

    function scheduleReconnect() {
      const delay = RECONNECT_DELAYS[Math.min(retryCount.current, RECONNECT_DELAYS.length - 1)];
      retryCount.current++;
      retryTimer.current = setTimeout(connect, delay);
    }

    connect();

    return () => {
      intentionalClose.current = true;
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
        retryTimer.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [engine]);
}
