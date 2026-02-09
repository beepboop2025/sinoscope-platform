import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';
import type { CoinGeckoMarketItem, CoinDetail } from '../../types';

interface CryptoPriceData {
  [coinId: string]: {
    usd: number;
    usd_24h_change?: number;
    usd_market_cap?: number;
  };
}

export async function fetchCryptoMarkets(vs: string = 'usd', perPage: number = 20): Promise<CoinGeckoMarketItem[] | null> {
  // Collector-first: pre-fetched crypto markets (top 50)
  if (vs === 'usd') {
    const collected = await getCollectorData('crypto_markets');
    if (collected) return (collected as CoinGeckoMarketItem[]).slice(0, perPage);
  }

  const cacheKey = `crypto_markets_${vs}_${perPage}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as CoinGeckoMarketItem[];

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const url = `${API.COINGECKO.markets}?vs_currency=${vs}&order=market_cap_desc&per_page=${perPage}&page=1&sparkline=true&price_change_percentage=1h,24h,7d`;
    const res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error(`CoinGecko: ${res.status}`);
    const data: unknown = await res.json();
    cacheSet(cacheKey, data, 30000);
    return data as CoinGeckoMarketItem[];
  } catch (err) {
    console.warn('[CryptoAPI]', (err as Error).message);
    return null;
  }
}

export async function fetchCryptoPrices(ids: string = 'bitcoin,ethereum,binancecoin,solana'): Promise<CryptoPriceData | null> {
  const cacheKey = `crypto_prices_${ids}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as CryptoPriceData;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const url = `${API.COINGECKO.prices}?ids=${ids}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true`;
    const res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error(`CoinGecko prices: ${res.status}`);
    const data: unknown = await res.json();
    cacheSet(cacheKey, data, 30000);
    return data as CryptoPriceData;
  } catch (err) {
    console.warn('[CryptoAPI prices]', (err as Error).message);
    return null;
  }
}

export async function fetchCoinDetail(coinId: string): Promise<CoinDetail | null> {
  const cacheKey = `coin_detail_${coinId}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached as CoinDetail;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetchWithTimeout(API.COINGECKO.coin(coinId));
    if (!res.ok) throw new Error(`CoinGecko coin: ${res.status}`);
    const data = await res.json() as Record<string, unknown>;

    const marketData = data.market_data as Record<string, unknown> | undefined;
    const links = data.links as Record<string, unknown> | undefined;
    const description = data.description as Record<string, string> | undefined;

    const result: CoinDetail = {
      name: data.name as string,
      symbol: data.symbol as string,
      market_cap: (marketData?.market_cap as Record<string, number>)?.usd || 0,
      total_supply: (marketData?.total_supply as number) || 0,
      description: (description?.en || '').slice(0, 500),
      links: {
        homepage: ((links?.homepage as string[]) || [])[0] || '',
        blockchain_site: ((links?.blockchain_site as string[]) || [])[0] || '',
        subreddit: (links?.subreddit_url as string) || '',
        github: (((links?.repos_url as Record<string, string[]>)?.github) || [])[0] || '',
      },
    };

    cacheSet(cacheKey, result, 120000);
    return result;
  } catch (err) {
    console.warn('[CryptoAPI coin detail]', (err as Error).message);
    return null;
  }
}
