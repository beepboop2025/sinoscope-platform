import { rand, randInt } from '../utils/math';
import type { MarketTick } from '../types/market';

interface CryptoBase {
  price: number;
  name: string;
  mcap: number;
}

const CRYPTOS: Record<string, CryptoBase> = {
  BTC: { price: 67500, name: 'Bitcoin', mcap: 1320e9 },
  ETH: { price: 3400, name: 'Ethereum', mcap: 408e9 },
  BNB: { price: 580, name: 'Binance Coin', mcap: 89e9 },
  SOL: { price: 145, name: 'Solana', mcap: 63e9 },
  XRP: { price: 0.62, name: 'Ripple', mcap: 34e9 },
  ADA: { price: 0.48, name: 'Cardano', mcap: 17e9 },
  DOGE: { price: 0.165, name: 'Dogecoin', mcap: 23e9 },
  DOT: { price: 7.2, name: 'Polkadot', mcap: 9.6e9 },
};

interface CryptoTick extends MarketTick {
  marketCap: number;
}

export function generateMockCrypto(): Record<string, CryptoTick> {
  const result: Record<string, CryptoTick> = {};
  for (const [sym, info] of Object.entries(CRYPTOS)) {
    const drift = rand(-0.03, 0.03);
    const price = +(info.price * (1 + drift)).toFixed(sym === 'BTC' ? 2 : 4);
    const change = +(price - info.price).toFixed(4);
    result[sym] = {
      symbol: sym,
      name: info.name,
      price,
      change,
      changePct: +((change / info.price) * 100).toFixed(2),
      volume: randInt(1e8, 5e9),
      marketCap: info.mcap,
      high: +(price * 1.02).toFixed(2),
      low: +(price * 0.98).toFixed(2),
      timestamp: Date.now(),
      market: 'crypto',
      mock: true,
    };
  }
  return result;
}
