import { rand, randInt } from '../utils/math';
import type { MarketTick } from '../types/market';

const STOCKS: Record<string, { price: number; name: string }> = {
  AAPL: { price: 188, name: 'Apple' }, MSFT: { price: 415, name: 'Microsoft' },
  GOOGL: { price: 155, name: 'Alphabet' }, AMZN: { price: 185, name: 'Amazon' },
  NVDA: { price: 880, name: 'NVIDIA' }, TSLA: { price: 195, name: 'Tesla' },
  META: { price: 505, name: 'Meta' }, JPM: { price: 195, name: 'JPMorgan' },
  V: { price: 280, name: 'Visa' }, JNJ: { price: 155, name: 'J&J' },
};

export function generateMockStocks(): Record<string, MarketTick> {
  const result: Record<string, MarketTick> = {};
  for (const [sym, info] of Object.entries(STOCKS)) {
    const drift = rand(-0.02, 0.02);
    const price = +(info.price * (1 + drift)).toFixed(2);
    const change = +(price - info.price).toFixed(2);
    result[sym] = {
      symbol: sym,
      name: info.name,
      price,
      change,
      changePct: +((change / info.price) * 100).toFixed(2),
      volume: randInt(1000000, 50000000),
      high: +(price * 1.01).toFixed(2),
      low: +(price * 0.99).toFixed(2),
      open: info.price,
      timestamp: Date.now(),
      market: 'stock',
      mock: true,
    };
  }
  return result;
}
