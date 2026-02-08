import { createWSConnection, closeWSConnection, sendWSMessage } from './WebSocketManager';

const BINANCE_WS = 'wss://stream.binance.com:9443/ws';

export function subscribeBinanceTickers(pairs, onTick) {
  const streams = pairs.map(p => `${p.toLowerCase()}@ticker`).join('/');
  const url = `${BINANCE_WS}/${streams}`;

  return createWSConnection('binance', url, {
    onMessage: (data) => {
      if (data.e === '24hrTicker') {
        onTick({
          symbol: data.s,
          price: parseFloat(data.c),
          change: parseFloat(data.p),
          changePct: parseFloat(data.P),
          volume: parseFloat(data.v),
          high: parseFloat(data.h),
          low: parseFloat(data.l),
          timestamp: data.E,
        });
      }
    },
    onOpen: () => console.log('[Binance WS] Connected'),
    onClose: () => console.log('[Binance WS] Disconnected'),
  });
}

export function unsubscribeBinance() {
  closeWSConnection('binance');
}
