import { getCollectorData } from '../CollectorClient';
import type { CoinGeckoMarketItem } from '../../types';

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

export async function fetchCryptoGlobal(): Promise<CryptoGlobalData | null> {
  const collected = await getCollectorData('crypto_global');
  if (collected) return collected as CryptoGlobalData;
  return null;
}

export async function fetchTrendingCoins(): Promise<TrendingCoin[] | null> {
  const collected = await getCollectorData('crypto_trending');
  if (collected) return collected as TrendingCoin[];
  return null;
}

// Derive top movers from pre-fetched crypto markets data
export async function fetchTopMovers(): Promise<CryptoMover[] | null> {
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
  return null;
}
