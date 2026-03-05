export type MarketType = 'stock' | 'crypto' | 'forex' | 'bond' | 'commodity' | 'index' | 'economic';

export interface MarketTick {
  symbol: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
  high: number;
  low: number;
  open?: number;
  timestamp: number;
  market: MarketType;
  mock?: boolean;
  name?: string;
  [key: string]: unknown;
}

export interface CryptoAsset {
  id: string;
  symbol: string;
  name: string;
  image?: string;
  current_price: number;
  market_cap: number;
  market_cap_rank?: number;
  total_volume: number;
  high_24h: number;
  low_24h: number;
  price_change_24h: number;
  price_change_percentage_24h: number;
  price_change_percentage_1h_in_currency?: number;
  price_change_percentage_7d_in_currency?: number;
  sparkline_in_7d?: { price: number[] };
  circulating_supply?: number;
  total_supply?: number;
  ath?: number;
  ath_change_percentage?: number;
}

export interface CoinDetail {
  name: string;
  symbol: string;
  market_cap: number;
  total_supply: number;
  description: string;
  links: {
    homepage: string;
    blockchain_site: string;
    subreddit: string;
    github: string;
  };
}

export interface ForexPair {
  symbol: string;
  base: string;
  quote: string;
  name: string;
}

export interface ForexRates {
  base: string;
  date: string;
  rates: Record<string, number>;
  timestamp: number;
}

export interface ForexTimeseries {
  base: string;
  start_date: string;
  end_date: string;
  rates: Record<string, Record<string, number>>;
}

export interface OHLCData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BondYield {
  maturity: string;
  yield: number;
  change?: number;
  timestamp?: number;
}

export interface CommodityData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  unit: string;
  timestamp: number;
}

export interface EconomicDataPoint {
  date: string;
  value: number;
  realtime_start?: string;
  realtime_end?: string;
}

export interface IndexData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  exchange: string;
  timestamp: number;
}

export interface MarketSnapshot {
  forex: Record<string, MarketTick>;
  stocks: Record<string, MarketTick>;
  crypto: Record<string, MarketTick>;
  bonds: BondYield[];
  commodities: Record<string, CommodityData>;
  economic: Record<string, EconomicDataPoint[]>;
  indices: Record<string, IndexData>;
  errors: Record<string, unknown>;
  lastUpdate: Record<string, number>;
  lastFetchTime: Record<string, number>;
}

export interface StockSymbol {
  symbol: string;
  name: string;
  exchange: string;
}

export interface CryptoSymbol {
  symbol: string;
  name: string;
  pair: string;
}

export interface CommoditySymbol {
  symbol: string;
  name: string;
  unit: string;
}

export interface IndexSymbol {
  symbol: string;
  name: string;
  exchange: string;
}

export interface StockProfile {
  symbol: string;
  companyName: string;
  exchange: string;
  industry: string;
  sector: string;
  description: string;
  ceo: string;
  website: string;
  image: string;
  mktCap: number;
  employees: number;
  ipoDate: string;
}

export interface MarketMover {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changesPercentage: number;
}

export interface EarningsEvent {
  date: string;
  epsActual: number | null;
  epsEstimate: number | null;
  revenueActual: number | null;
  revenueEstimate: number | null;
  symbol: string;
  hour: string;
  quarter: number;
  year: number;
}

export interface EconomicIndicator {
  name: string;
  unit: string;
  frequency: string;
}

export interface SectorPerformance {
  sector: string;
  changesPercentage: string;
}

export interface FearGreedData {
  value: number;
  description: string;
  timestamp: number;
}
