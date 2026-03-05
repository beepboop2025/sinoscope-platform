/**
 * Client for on-demand backend proxy endpoints.
 *
 * The Celery collector pre-fetches bulk data (forex rates, crypto markets, etc.)
 * and stores it in Redis. But some features need on-demand lookups (individual
 * stock profiles, candle data, earnings). These go through /api/proxy/* endpoints
 * which fetch from external APIs using server-side keys with Redis caching.
 */

import { cacheGet, cacheSet } from './CacheManager';

const API_BASE: string = import.meta.env.VITE_API_BASE_URL || '';
const FETCH_TIMEOUT: number = 15_000;

async function proxyFetch<T>(path: string, cacheKey: string, ttl: number): Promise<T | null> {
  const cached = cacheGet(cacheKey);
  if (cached) return cached as T;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT);
    const res = await fetch(`${API_BASE}/api/proxy/${path}`, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) return null;
    const data: T = await res.json();
    if (data !== null && data !== undefined) {
      cacheSet(cacheKey, data, ttl);
    }
    return data;
  } catch {
    return null;
  }
}

// ── Stock Data ─────────────────────────────────────────────────────────────

export function getStockProfile(symbol: string) {
  return proxyFetch(`stock-profile/${encodeURIComponent(symbol)}`, `proxy_profile_${symbol}`, 300000);
}

export function getFinnhubQuote(symbol: string) {
  return proxyFetch(`finnhub-quote/${encodeURIComponent(symbol)}`, `proxy_fhquote_${symbol}`, 15000);
}

export function getMarketMovers(type: string = 'gainers') {
  return proxyFetch(`market-movers/${type}`, `proxy_movers_${type}`, 120000);
}

export function getHistoricalPrices(symbol: string) {
  return proxyFetch(`historical/${encodeURIComponent(symbol)}`, `proxy_hist_${symbol}`, 300000);
}

export function getCandles(symbol: string, resolution: string, from: number, to: number) {
  return proxyFetch(
    `candles/${encodeURIComponent(symbol)}?resolution=${resolution}&from=${from}&to=${to}`,
    `proxy_candles_${symbol}_${resolution}_${from}_${to}`,
    60000,
  );
}

export function getEarningsCalendar(from: string, to: string) {
  return proxyFetch(`earnings?from=${from}&to=${to}`, `proxy_earnings_${from}_${to}`, 3600000);
}

// ── Crypto ─────────────────────────────────────────────────────────────────

export function getCoinDetail(coinId: string) {
  return proxyFetch(`coin-detail/${encodeURIComponent(coinId)}`, `proxy_coin_${coinId}`, 120000);
}

// ── Bonds & Commodities ────────────────────────────────────────────────────

export function getYield(maturity: string) {
  return proxyFetch(`yield/${maturity}`, `proxy_yield_${maturity}`, 600000);
}

export function getCommodity(name: string) {
  return proxyFetch(`commodity/${name}`, `proxy_commodity_${name}`, 600000);
}

// ── Economic ───────────────────────────────────────────────────────────────

export function getEconIndicator(indicator: string) {
  return proxyFetch(`econ/${indicator}`, `proxy_econ_${indicator}`, 600000);
}

export function getWorldBank(country: string, indicator: string) {
  return proxyFetch(
    `worldbank/${encodeURIComponent(country)}/${encodeURIComponent(indicator)}`,
    `proxy_wb_${country}_${indicator}`,
    21600000,
  );
}
