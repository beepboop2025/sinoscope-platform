import type { MarketType } from '../types';

export const MARKET_TYPES = {
  FOREX: 'forex',
  STOCK: 'stock',
  BOND: 'bond',
  COMMODITY: 'commodity',
  CRYPTO: 'crypto',
  INDEX: 'index',
  ECONOMIC: 'economic',
} as const satisfies Record<string, MarketType>;
