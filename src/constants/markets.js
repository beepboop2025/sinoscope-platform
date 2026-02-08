export const MARKET_TYPES = {
  FOREX: 'forex',
  STOCK: 'stock',
  BOND: 'bond',
  COMMODITY: 'commodity',
  CRYPTO: 'crypto',
  INDEX: 'index',
  ECONOMIC: 'economic',
};

export const MARKET_COLORS = {
  forex: 'var(--cyan)',
  stock: 'var(--blue)',
  bond: 'var(--purple)',
  commodity: 'var(--amber)',
  crypto: 'var(--orange)',
  index: 'var(--green)',
  economic: 'var(--teal)',
};

export const EXCHANGES = {
  NYSE: { name: 'New York Stock Exchange', country: 'US', tz: 'America/New_York' },
  NASDAQ: { name: 'NASDAQ', country: 'US', tz: 'America/New_York' },
  SSE: { name: 'Shanghai Stock Exchange', country: 'CN', tz: 'Asia/Shanghai' },
  SZSE: { name: 'Shenzhen Stock Exchange', country: 'CN', tz: 'Asia/Shanghai' },
  HKEX: { name: 'Hong Kong Exchanges', country: 'HK', tz: 'Asia/Hong_Kong' },
  LSE: { name: 'London Stock Exchange', country: 'GB', tz: 'Europe/London' },
  TSE: { name: 'Tokyo Stock Exchange', country: 'JP', tz: 'Asia/Tokyo' },
  NSE: { name: 'National Stock Exchange', country: 'IN', tz: 'Asia/Kolkata' },
};
