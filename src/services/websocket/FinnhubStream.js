import { createWSConnection, closeWSConnection, sendWSMessage } from './WebSocketManager';

export function subscribeFinnhubTrades(symbols, onTrade) {
  const key = import.meta.env.VITE_FINNHUB_API_KEY;
  if (!key) return null;

  const url = `wss://ws.finnhub.io?token=${key}`;

  return createWSConnection('finnhub', url, {
    onMessage: (data) => {
      if (data.type === 'trade' && data.data) {
        for (const trade of data.data) {
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

export function unsubscribeFinnhub() {
  closeWSConnection('finnhub');
}
