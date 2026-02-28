import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';
import type { CoinGeckoMarketItem } from '../../types';

// Uses existing coingecko rate limiter

interface CryptoGlobalData {
  totalMarketCap: number;
  totalVolume: number;
  btcDominance: number;
  ethDominance: number;
  activeCryptos: number;
  markets: number;
  marketCapChange24h: number;
  updatedAt?: number;
}

interface TrendingCoin {
  id: string;
  name: string;
  symbol: string;
  rank: number;
  thumb?: string;
  priceBtc?: number;
  score: number;
}

interface CryptoMover {
  id: string;
  symbol: string;
  name: string;
  price: number;
  change24h: number;
  marketCap: number;
  volume: number;
  rank: number;
}

// Global market data
export async function fetchCryptoGlobal(): Promise<CryptoGlobalData | null> {
  // Collector-first: pre-fetched global crypto data
  const collected = await getCollectorData('crypto_global');
  if (collected) return collected as CryptoGlobalData;

  const cacheKey = 'coingecko_global';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as CryptoGlobalData;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetchWithTimeout('https://api.coingecko.com/api/v3/global');
    if (!res.ok) throw new Error(`CoinGecko global: ${res.status}`);
    const data = await res.json() as { data: Record<string, unknown> };
    const d = data.data;

    const result: CryptoGlobalData = {
      totalMarketCap: (d.total_market_cap as Record<string, number>)?.usd || 0,
      totalVolume: (d.total_volume as Record<string, number>)?.usd || 0,
      btcDominance: (d.market_cap_percentage as Record<string, number>)?.btc || 0,
      ethDominance: (d.market_cap_percentage as Record<string, number>)?.eth || 0,
      activeCryptos: (d.active_cryptocurrencies as number) || 0,
      markets: (d.markets as number) || 0,
      marketCapChange24h: (d.market_cap_change_percentage_24h_usd as number) || 0,
      updatedAt: d.updated_at as number,
    };

    cacheSet(cacheKey, result, 120000);
    return result;
  } catch (err) {
    console.warn('[CoinGecko global]', (err as Error).message);
    return null;
  }
}

// Trending coins
export async function fetchTrendingCoins(): Promise<TrendingCoin[] | null> {
  // Collector-first: pre-fetched trending coins
  const collected = await getCollectorData('crypto_trending');
  if (collected) return collected as TrendingCoin[];

  const cacheKey = 'coingecko_trending';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as TrendingCoin[];

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetchWithTimeout('https://api.coingecko.com/api/v3/search/trending');
    if (!res.ok) throw new Error(`CoinGecko trending: ${res.status}`);
    const data = await res.json() as { coins?: { item: Record<string, unknown> }[] };

    const coins: TrendingCoin[] = (data.coins || []).map((c: { item: Record<string, unknown> }): TrendingCoin => ({
      id: c.item.id as string,
      name: c.item.name as string,
      symbol: c.item.symbol as string,
      rank: c.item.market_cap_rank as number,
      thumb: c.item.thumb as string,
      priceBtc: c.item.price_btc as number,
      score: c.item.score as number,
    }));

    cacheSet(cacheKey, coins, 300000);
    return coins;
  } catch (err) {
    console.warn('[CoinGecko trending]', (err as Error).message);
    return null;
  }
}

// Top gainers/losers from markets
export async function fetchTopMovers(): Promise<CryptoMover[] | null> {
  // Collector-first: derive movers from pre-fetched crypto markets
  const collected = await getCollectorData('crypto_markets');
  if (collected && (collected as CoinGeckoMarketItem[]).length > 0) {
    const sorted = [...(collected as CoinGeckoMarketItem[])].sort((a, b) =>
      Math.abs(b.price_change_percentage_24h || 0) - Math.abs(a.price_change_percentage_24h || 0)
    );
    return sorted.slice(0, 20).map((c: CoinGeckoMarketItem): CryptoMover => ({
      id: c.id,
      symbol: c.symbol?.toUpperCase(),
      name: c.name,
      price: c.current_price,
      change24h: c.price_change_percentage_24h,
      marketCap: c.market_cap,
      volume: c.total_volume,
      rank: c.market_cap_rank,
    }));
  }

  const cacheKey = 'coingecko_movers';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as CryptoMover[];

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetchWithTimeout('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h');
    if (!res.ok) throw new Error(`CoinGecko markets: ${res.status}`);
    const data: unknown = await res.json();

    const sorted = [...(data as CoinGeckoMarketItem[])].sort((a, b) =>
      Math.abs(b.price_change_percentage_24h || 0) - Math.abs(a.price_change_percentage_24h || 0)
    );

    const movers: CryptoMover[] = sorted.slice(0, 20).map((c: CoinGeckoMarketItem): CryptoMover => ({
      id: c.id,
      symbol: c.symbol?.toUpperCase(),
      name: c.name,
      price: c.current_price,
      change24h: c.price_change_percentage_24h,
      marketCap: c.market_cap,
      volume: c.total_volume,
      rank: c.market_cap_rank,
    }));

    cacheSet(cacheKey, movers, 120000);
    return movers;
  } catch (err) {
    console.warn('[CoinGecko movers]', (err as Error).message);
    return null;
  }
}

export function getMockCryptoGlobal(): CryptoGlobalData {
  return {
    totalMarketCap: 2480000000000,
    totalVolume: 98000000000,
    btcDominance: 52.3,
    ethDominance: 16.8,
    activeCryptos: 14200,
    markets: 920,
    marketCapChange24h: 1.24,
  };
}

export function getMockTrending(): TrendingCoin[] {
  return [
    { id: 'pepe', name: 'Pepe', symbol: 'PEPE', rank: 24, score: 0 },
    { id: 'bonk', name: 'Bonk', symbol: 'BONK', rank: 58, score: 1 },
    { id: 'sui', name: 'Sui', symbol: 'SUI', rank: 12, score: 2 },
    { id: 'render-token', name: 'Render', symbol: 'RENDER', rank: 30, score: 3 },
    { id: 'injective-protocol', name: 'Injective', symbol: 'INJ', rank: 35, score: 4 },
    { id: 'celestia', name: 'Celestia', symbol: 'TIA', rank: 42, score: 5 },
    { id: 'jupiter', name: 'Jupiter', symbol: 'JUP', rank: 65, score: 6 },
  ];
}
