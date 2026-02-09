import { createWSConnection, closeWSConnection, sendWSMessage } from './WebSocketManager';

interface FinnhubTradeData {
  type: string;
  data?: Array<{
    s: string;
    p: number;
    v: number;
    t: number;
  }>;
}

interface FinnhubTrade {
  symbol: string;
  price: number;
  volume: number;
  timestamp: number;
}

export function subscribeFinnhubTrades(symbols: string[], onTrade: (trade: FinnhubTrade) => void): ReturnType<typeof createWSConnection> | null {
  const key = import.meta.env.VITE_FINNHUB_API_KEY as string | undefined;
  if (!key) return null;

  const url = `wss://ws.finnhub.io?token=${key}`;

  return createWSConnection('finnhub', url, {
    onMessage: (data: unknown) => {
      const msg = data as FinnhubTradeData;
      if (msg.type === 'trade' && msg.data) {
        for (const trade of msg.data) {
          onTrade({
            symbol: trade.s,
            price: trade.p,
            volume: trade.v,
            timestamp: trade.t,
          });
        }
      }
    },
    onOpen: () => {
      console.log('[Finnhub WS] Connected');
      for (const sym of symbols) {
        sendWSMessage('finnhub', { type: 'subscribe', symbol: sym });
      }
    },
    onClose: () => console.log('[Finnhub WS] Disconnected'),
  });
}

export function unsubscribeFinnhub(): void {
  closeWSConnection('finnhub');
}
