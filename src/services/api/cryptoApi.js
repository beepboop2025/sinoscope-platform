import { API } from '../../constants/apiEndpoints';
import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken } from '../RateLimiter';

export async function fetchCryptoMarkets(vs = 'usd', perPage = 20) {
  const cacheKey = `crypto_markets_${vs}_${perPage}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('coingecko')) return null;
  consumeToken('coingecko');

  try {
    const url = `${API.COINGECKO.markets}?vs_currency=${vs}&order=market_cap_desc&per_page=${perPage}&page=1&sparkline=true&price_change_percentage=1h,24h,7d`;
    const res = await fetch(url);
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
    const res = await fetch(url);
    if (!res.ok) throw new Error(`CoinGecko prices: ${res.status}`);
    const data = await res.json();
    cacheSet(cacheKey, data, 30000);
    return data;
  } catch (err) {
    console.warn('[CryptoAPI prices]', err.message);
    return null;
  }
}
