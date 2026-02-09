import { rand } from '../utils/math';
import type { MarketTick } from '../types/market';

const BASE_RATES: Record<string, number> = {
  'USD/EUR': 0.92, 'USD/GBP': 0.79, 'USD/JPY': 154.5, 'USD/CHF': 0.88,
  'USD/AUD': 1.53, 'USD/CAD': 1.36, 'USD/NZD': 1.65, 'USD/CNY': 7.24,
  'USD/CNH': 7.25, 'USD/HKD': 7.82, 'USD/INR': 83.2, 'EUR/GBP': 0.86,
  'EUR/JPY': 168.1,
};

export function generateMockForex(): Record<string, MarketTick> {
  const result: Record<string, MarketTick> = {};
  for (const [pair, base] of Object.entries(BASE_RATES)) {
    const drift = rand(-0.003, 0.003);
    const price = +(base * (1 + drift)).toFixed(4);
    const change = +(price - base).toFixed(4);
    result[pair] = {
      symbol: pair,
      price,
      change,
      changePct: +((change / base) * 100).toFixed(2),
      high: +(price * 1.002).toFixed(4),
      low: +(price * 0.998).toFixed(4),
      open: base,
      volume: 0,
      timestamp: Date.now(),
      market: 'forex',
      mock: true,
    };
  }
  return result;
}
