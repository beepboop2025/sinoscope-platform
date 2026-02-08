import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';

// Uses existing coingecko rate limiter

// Global market data
export async function fetchCryptoGlobal() {
  // Collector-first: pre-fetched global crypto data
  const collected = await getCollectorData('crypto_global');
  if (collected) return collected;

  const cacheKey = 'coingecko_global';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetch('https://api.coingecko.com/api/v3/global');
    if (!res.ok) throw new Error(`CoinGecko global: ${res.status}`);
    const data = await res.json();
    const d = data.data;

    const result = {
      totalMarketCap: d.total_market_cap?.usd || 0,
      totalVolume: d.total_volume?.usd || 0,
      btcDominance: d.market_cap_percentage?.btc || 0,
      ethDominance: d.market_cap_percentage?.eth || 0,
      activeCryptos: d.active_cryptocurrencies || 0,
      markets: d.markets || 0,
      marketCapChange24h: d.market_cap_change_percentage_24h_usd || 0,
      updatedAt: d.updated_at,
    };

    cacheSet(cacheKey, result, 120000);
    return result;
  } catch (err) {
    console.warn('[CoinGecko global]', err.message);
    return null;
  }
}

// Trending coins
export async function fetchTrendingCoins() {
  // Collector-first: pre-fetched trending coins
  const collected = await getCollectorData('crypto_trending');
  if (collected) return collected;

  const cacheKey = 'coingecko_trending';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetch('https://api.coingecko.com/api/v3/search/trending');
    if (!res.ok) throw new Error(`CoinGecko trending: ${res.status}`);
    const data = await res.json();

    const coins = (data.coins || []).map(c => ({
      id: c.item.id,
      name: c.item.name,
      symbol: c.item.symbol,
      rank: c.item.market_cap_rank,
      thumb: c.item.thumb,
      priceBtc: c.item.price_btc,
      score: c.item.score,
    }));

    cacheSet(cacheKey, coins, 300000);
    return coins;
  } catch (err) {
    console.warn('[CoinGecko trending]', err.message);
    return null;
  }
}

// Top gainers/losers from markets
export async function fetchTopMovers() {
  // Collector-first: derive movers from pre-fetched crypto markets
  const collected = await getCollectorData('crypto_markets');
  if (collected && collected.length > 0) {
    const sorted = [...collected].sort((a, b) =>
      Math.abs(b.price_change_percentage_24h || 0) - Math.abs(a.price_change_percentage_24h || 0)
    );
    return sorted.slice(0, 20).map(c => ({
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
  if (cached) return cached;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h');
    if (!res.ok) throw new Error(`CoinGecko markets: ${res.status}`);
    const data = await res.json();

    const sorted = [...data].sort((a, b) =>
      Math.abs(b.price_change_percentage_24h || 0) - Math.abs(a.price_change_percentage_24h || 0)
    );

    const movers = sorted.slice(0, 20).map(c => ({
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
    console.warn('[CoinGecko movers]', err.message);
    return null;
  }
}

export function getMockCryptoGlobal() {
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

export function getMockTrending() {
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
