import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

export async function fetchCryptoMarkets(vs = 'usd', perPage = 20) {
  // Collector-first: pre-fetched crypto markets (top 50)
  if (vs === 'usd') {
    const collected = await getCollectorData('crypto_markets');
    if (collected) return collected.slice(0, perPage);
  }

  const cacheKey = `crypto_markets_${vs}_${perPage}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const url = `${API.COINGECKO.markets}?vs_currency=${vs}&order=market_cap_desc&per_page=${perPage}&page=1&sparkline=true&price_change_percentage=1h,24h,7d`;
    const res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error(`CoinGecko: ${res.status}`);
    const data = await res.json();
    cacheSet(cacheKey, data, 30000);
    return data;
  } catch (err) {
    console.warn('[CryptoAPI]', err.message);
    return null;
  }
}

export async function fetchCryptoPrices(ids = 'bitcoin,ethereum,binancecoin,solana') {
  const cacheKey = `crypto_prices_${ids}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const url = `${API.COINGECKO.prices}?ids=${ids}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true`;
    const res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error(`CoinGecko prices: ${res.status}`);
    const data = await res.json();
    cacheSet(cacheKey, data, 30000);
    return data;
  } catch (err) {
    console.warn('[CryptoAPI prices]', err.message);
    return null;
  }
}

export async function fetchCoinDetail(coinId) {
  const cacheKey = `coin_detail_${coinId}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const res = await fetchWithTimeout(API.COINGECKO.coin(coinId));
    if (!res.ok) throw new Error(`CoinGecko coin: ${res.status}`);
    const data = await res.json();

    const result = {
      name: data.name,
      symbol: data.symbol,
      market_cap: data.market_data?.market_cap?.usd || 0,
      total_supply: data.market_data?.total_supply || 0,
      description: (data.description?.en || '').slice(0, 500),
      links: {
        homepage: data.links?.homepage?.[0] || '',
        blockchain_site: data.links?.blockchain_site?.[0] || '',
        subreddit: data.links?.subreddit_url || '',
        github: data.links?.repos_url?.github?.[0] || '',
      },
    };

    cacheSet(cacheKey, result, 120000);
    return result;
  } catch (err) {
    console.warn('[CryptoAPI coin detail]', err.message);
    return null;
  }
}
