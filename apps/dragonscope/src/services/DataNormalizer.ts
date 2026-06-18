import type { MarketTick, MarketType } from '../types/market';

interface RawTickData {
  symbol?: string;
  s?: string;
  price?: number | string;
  c?: number | string;
  p?: number | string;
  change?: number | string;
  d?: number | string;
  changePct?: number | string;
  dp?: number | string;
  changesPercentage?: number | string;
  volume?: number | string;
  v?: number | string;
  high?: number | string;
  h?: number | string;
  low?: number | string;
  l?: number | string;
  open?: number | string;
  o?: number | string;
  timestamp?: number;
  t?: number;
}

interface RawCryptoData {
  symbol?: string;
  id?: string;
  name?: string;
  current_price?: number | string;
  price?: number | string;
  price_change_24h?: number | string;
  price_change_percentage_24h?: number | string;
  total_volume?: number | string;
  market_cap?: number | string;
  high_24h?: number | string;
  low_24h?: number | string;
}

interface NormalizedCrypto extends MarketTick {
  name: string;
  marketCap: number;
}

interface RawOHLCData {
  t?: number | string;
  date?: number | string;
  timestamp?: number | string;
  o?: number | string;
  open?: number | string;
  h?: number | string;
  high?: number | string;
  l?: number | string;
  low?: number | string;
  c?: number | string;
  close?: number | string;
  v?: number | string;
  volume?: number | string;
}

interface NormalizedOHLC {
  time: number | string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export function normalizeTick(raw: RawTickData, market: MarketType): MarketTick {
  return {
    symbol: raw.symbol || raw.s || '',
    price: Number(raw.price ?? raw.c ?? raw.p ?? 0),
    change: Number(raw.change ?? raw.d ?? 0),
    changePct: Number(raw.changePct ?? raw.dp ?? raw.changesPercentage ?? 0),
    volume: Number(raw.volume ?? raw.v ?? 0),
    high: Number(raw.high ?? raw.h ?? 0),
    low: Number(raw.low ?? raw.l ?? 0),
    open: Number(raw.open ?? raw.o ?? 0),
    timestamp: raw.timestamp ?? raw.t ?? Date.now(),
    market,
  };
}

export function normalizeForex(pair: string, data: unknown): MarketTick {
  const rate: number = Number(data) || 0;
  return {
    symbol: pair,
    price: rate,
    change: 0,
    changePct: 0,
    volume: 0,
    high: rate,
    low: rate,
    open: rate,
    timestamp: Date.now(),
    market: 'forex',
  };
}

export function normalizeCrypto(data: RawCryptoData): NormalizedCrypto {
  return {
    symbol: (data.symbol || data.id || '').toUpperCase(),
    name: data.name || '',
    price: Number(data.current_price ?? data.price ?? 0),
    change: Number(data.price_change_24h ?? 0),
    changePct: Number(data.price_change_percentage_24h ?? 0),
    volume: Number(data.total_volume ?? 0),
    marketCap: Number(data.market_cap ?? 0),
    high: Number(data.high_24h ?? 0),
    low: Number(data.low_24h ?? 0),
    timestamp: Date.now(),
    market: 'crypto',
  };
}

export function normalizeOHLC(data: RawOHLCData): NormalizedOHLC {
  return {
    time: data.t || data.date || data.timestamp || 0,
    open: Number(data.o ?? data.open ?? 0),
    high: Number(data.h ?? data.high ?? 0),
    low: Number(data.l ?? data.low ?? 0),
    close: Number(data.c ?? data.close ?? 0),
    volume: Number(data.v ?? data.volume ?? 0),
  };
}
