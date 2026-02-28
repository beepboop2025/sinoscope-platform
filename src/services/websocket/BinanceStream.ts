import { createWSConnection, closeWSConnection } from './WebSocketManager';
import type { BinanceTickerMessage } from '../../types/api';
import type { MarketTick } from '../../types/market';

const BINANCE_WS = 'wss://stream.binance.com:9443/ws';

interface BinanceTick {
  symbol: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
  high: number;
  low: number;
  timestamp: number;
}

export function subscribeBinanceTickers(pairs: string[], onTick: (tick: BinanceTick) => void): ReturnType<typeof createWSConnection> {
  const streams = pairs.map(p => `${p.toLowerCase()}@ticker`).join('/');
  const url = `${BINANCE_WS}/${streams}`;

  return createWSConnection('binance', url, {
    onMessage: (data: unknown) => {
      const msg = data as BinanceTickerMessage;
      if (msg.e === '24hrTicker') {
        onTick({
          symbol: msg.s,
          price: parseFloat(msg.c),
          change: parseFloat(msg.p),
          changePct: parseFloat(msg.P),
          volume: parseFloat(msg.v),
          high: parseFloat(msg.h),
          low: parseFloat(msg.l),
          timestamp: msg.E,
        });
      }
    },
    onOpen: () => console.log('[Binance WS] Connected'),
    onClose: () => console.log('[Binance WS] Disconnected'),
  });
}

export function unsubscribeBinance(): void {
  closeWSConnection('binance');
}
