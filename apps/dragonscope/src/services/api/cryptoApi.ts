import { getCollectorData } from '../CollectorClient';
import { getCoinDetail as proxyCoinDetail } from '../BackendProxyClient';
import type { CoinGeckoMarketItem, CoinDetail } from '../../types';

interface CryptoPriceData {
  [coinId: string]: {
    usd: number;
    usd_24h_change?: number;
    usd_market_cap?: number;
  };
}

export async function fetchCryptoMarkets(vs: string = 'usd', perPage: number = 20): Promise<CoinGeckoMarketItem[] | null> {
  const collected = await getCollectorData('crypto_markets');
  if (collected) return (collected as CoinGeckoMarketItem[]).slice(0, perPage);
  return null;
}

export async function fetchCryptoPrices(ids: string = 'bitcoin,ethereum,binancecoin,solana'): Promise<CryptoPriceData | null> {
  // Derive prices from collector's crypto_markets data
  const collected = await getCollectorData('crypto_markets');
  if (collected) {
    const idSet = new Set(ids.split(','));
    const result: CryptoPriceData = {};
    for (const coin of collected as CoinGeckoMarketItem[]) {
      if (idSet.has(coin.id)) {
        result[coin.id] = {
          usd: coin.current_price,
          usd_24h_change: coin.price_change_percentage_24h,
          usd_market_cap: coin.market_cap,
        };
      }
    }
    if (Object.keys(result).length > 0) return result;
  }
  return null;
}

export async function fetchCoinDetail(coinId: string): Promise<CoinDetail | null> {
  return proxyCoinDetail(coinId) as Promise<CoinDetail | null>;
}
