export type AnomalyType = 'price_spike' | 'volume_spike' | 'divergence' | 'breakout';

export interface Anomaly {
  id: string;
  type: AnomalyType;
  symbol: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  value: number;
  threshold: number;
  timestamp: number;
}

export interface TechnicalIndicators {
  sma20: number | null;
  sma50: number | null;
  ema12: number | null;
  ema26: number | null;
  rsi: number | null;
  macd: MACDResult | null;
  bollinger: BollingerResult | null;
  atr: number | null;
}

export interface MACDResult {
  macd: number;
  signal: number;
  histogram: number;
}

export interface BollingerResult {
  upper: number;
  middle: number;
  lower: number;
  width: number;
}

export interface TrendAnalysis {
  direction: 'bullish' | 'bearish' | 'neutral';
  strength: number;
  signals: TechnicalSignal[];
}

export interface TechnicalSignal {
  type: string;
  signal: 'buy' | 'sell' | 'hold';
  description: string;
  strength: number;
}

export interface CorrelationMatrix {
  symbols: string[];
  matrix: number[][];
}

export interface CorrelatedPair {
  pair: [string, string];
  correlation: number;
  strength: 'strong' | 'moderate' | 'weak';
}

export interface TimelineEvent {
  id: string;
  type: string;
  title: string;
  description: string;
  symbol?: string;
  impact: 'positive' | 'negative' | 'neutral';
  severity: 'low' | 'medium' | 'high';
  timestamp: number;
  priceAtEvent?: number;
}

export interface PatternEvent {
  type: string;
  symbol: string;
  value: number;
  timestamp: number;
}

export interface CorrelationEngine {
  addPrice(symbol: string, price: number, timestamp?: number): void;
  getCorrelationMatrix(window?: number): CorrelationMatrix | null;
  findHighCorrelations(threshold?: number, window?: number): CorrelatedPair[];
}

export interface TechnicalEngine {
  addPrice(symbol: string, price: number, volume?: number): void;
  getIndicators(symbol: string): TechnicalIndicators;
  getTrend(symbol: string): TrendAnalysis;
}

export interface PatternEngineInstance {
  ingest(tick: { symbol: string; price: number; volume: number; timestamp: number }): Anomaly[];
  getRecent(n?: number): Anomaly[];
  getEventLog(): PatternEvent[];
}

export interface MarketEngineInstance {
  subscribe(cb: () => void): () => void;
  getSnapshot(): import('./market').MarketSnapshot;
  updateFromWS(tick: import('./market').MarketTick): void;
  fetchForex(): Promise<void>;
  fetchStocks(): Promise<void>;
  fetchCrypto(): Promise<void>;
  fetchBonds(): Promise<void>;
  fetchCommodities(): Promise<void>;
  fetchEconomic(): Promise<void>;
  fetchIndices(): Promise<void>;
  startPolling(): void;
  stopPolling(): void;
}
