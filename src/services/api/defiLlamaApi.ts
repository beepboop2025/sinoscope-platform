import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';
import { getCollectorData } from '../CollectorClient';
import { fetchWithTimeout } from '../../utils/helpers';

// DeFi Llama is free, no API key needed, generous limits
createRateLimiter('defillama', 20, 60000);

const BASE: string = 'https://api.llama.fi';
const YIELDS: string = 'https://yields.llama.fi';
const STABLECOINS: string = 'https://stablecoins.llama.fi';

interface DefiProtocol {
  name: string;
  symbol: string;
  tvl: number;
  change1h: number;
  change1d: number;
  change7d: number;
  category: string;
  chains: string[];
  url: string;
  logo: string;
}

interface TVLDataPoint {
  date: string;
  tvl: number;
}

interface ChainTVL {
  name: string;
  tvl: number;
  tokenSymbol: string;
  gecko_id: string;
}

interface DefiYieldPool {
  pool: string;
  project: string;
  symbol: string;
  chain: string;
  tvl: number;
  apy: number;
  apyBase: number;
  apyReward: number;
  stablecoin: boolean;
}

interface StablecoinData {
  name: string;
  symbol: string;
  pegType: string;
  circulating: number;
  price: number;
}

interface MockDefiData {
  protocols: { name: string; symbol: string; tvl: number; change1d: number; change7d: number; category: string; chains: string[] }[];
  chains: { name: string; tvl: number }[];
}

// Top DeFi protocols by TVL
export async function fetchDefiProtocols(): Promise<DefiProtocol[] | null> {
  // Collector-first: pre-fetched DeFi protocols
  const collected = await getCollectorData('defi_protocols');
  if (collected && (collected as DefiProtocol[]).length > 0) return collected as DefiProtocol[];

  const cacheKey = 'defi_protocols';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as DefiProtocol[];

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetchWithTimeout(`${BASE}/protocols`);
    if (!res.ok) throw new Error(`DeFi Llama protocols: ${res.status}`);
    const data: unknown = await res.json();

    const protocols: DefiProtocol[] = ((data as Record<string, unknown>[]) || []).slice(0, 50).map((p: Record<string, unknown>): DefiProtocol => ({
      name: p.name as string,
      symbol: (p.symbol || '') as string,
      tvl: (p.tvl || 0) as number,
      change1h: (p.change_1h || 0) as number,
      change1d: (p.change_1d || 0) as number,
      change7d: (p.change_7d || 0) as number,
      category: (p.category || '') as string,
      chains: ((p.chains || []) as string[]).slice(0, 5),
      url: (p.url || '') as string,
      logo: (p.logo || '') as string,
    }));

    cacheSet(cacheKey, protocols, 300000);
    return protocols;
  } catch (err) {
    console.warn('[DeFiLlama protocols]', (err as Error).message);
    return null;
  }
}

// Total TVL across all chains
export async function fetchDefiTVL(): Promise<TVLDataPoint[] | null> {
  const cacheKey = 'defi_tvl_total';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as TVLDataPoint[];

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetchWithTimeout(`${BASE}/v2/historicalChainTvl`);
    if (!res.ok) throw new Error(`DeFi Llama TVL: ${res.status}`);
    const data: unknown = await res.json();
    const recent: TVLDataPoint[] = ((data as { date: number; tvl: number }[]) || []).slice(-30).map((d: { date: number; tvl: number }): TVLDataPoint => ({
      date: new Date(d.date * 1000).toISOString().split('T')[0],
      tvl: d.tvl,
    }));
    cacheSet(cacheKey, recent, 300000);
    return recent;
  } catch (err) {
    console.warn('[DeFiLlama TVL]', (err as Error).message);
    return null;
  }
}

// Chain TVL breakdown
export async function fetchChainTVL(): Promise<ChainTVL[] | null> {
  // Collector-first: pre-fetched chain TVLs
  const collected = await getCollectorData('defi_chains');
  if (collected && (collected as ChainTVL[]).length > 0) return collected as ChainTVL[];

  const cacheKey = 'defi_chain_tvl';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as ChainTVL[];

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetchWithTimeout(`${BASE}/v2/chains`);
    if (!res.ok) throw new Error(`DeFi Llama chains: ${res.status}`);
    const data: unknown = await res.json();

    const chains: ChainTVL[] = ((data as Record<string, unknown>[]) || []).slice(0, 20).map((c: Record<string, unknown>): ChainTVL => ({
      name: c.name as string,
      tvl: (c.tvl || 0) as number,
      tokenSymbol: (c.tokenSymbol || '') as string,
      gecko_id: (c.gecko_id || '') as string,
    }));

    cacheSet(cacheKey, chains, 300000);
    return chains;
  } catch (err) {
    console.warn('[DeFiLlama chains]', (err as Error).message);
    return null;
  }
}

// Top DeFi yields
export async function fetchDefiYields(): Promise<DefiYieldPool[] | null> {
  // Collector-first: pre-fetched DeFi yields
  const collected = await getCollectorData('defi_yields');
  if (collected && (collected as DefiYieldPool[]).length > 0) return collected as DefiYieldPool[];

  const cacheKey = 'defi_yields';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as DefiYieldPool[];

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetchWithTimeout(`${YIELDS}/pools`);
    if (!res.ok) throw new Error(`DeFi Llama yields: ${res.status}`);
    const data = await res.json() as { data?: Record<string, unknown>[] };

    // Filter for reasonable yields with meaningful TVL
    const pools: DefiYieldPool[] = (data.data || [])
      .filter((p: Record<string, unknown>) => (p.tvlUsd as number) > 1000000 && (p.apy as number) > 0 && (p.apy as number) < 100)
      .sort((a: Record<string, unknown>, b: Record<string, unknown>) => (b.tvlUsd as number) - (a.tvlUsd as number))
      .slice(0, 40)
      .map((p: Record<string, unknown>): DefiYieldPool => ({
        pool: p.pool as string,
        project: p.project as string,
        symbol: p.symbol as string,
        chain: p.chain as string,
        tvl: p.tvlUsd as number,
        apy: p.apy as number,
        apyBase: (p.apyBase || 0) as number,
        apyReward: (p.apyReward || 0) as number,
        stablecoin: (p.stablecoin || false) as boolean,
      }));

    cacheSet(cacheKey, pools, 300000);
    return pools;
  } catch (err) {
    console.warn('[DeFiLlama yields]', (err as Error).message);
    return null;
  }
}

// Stablecoin market caps
export async function fetchStablecoins(): Promise<StablecoinData[] | null> {
  // Collector-first: pre-fetched stablecoin data
  const collected = await getCollectorData('defi_stablecoins');
  if (collected && (collected as StablecoinData[]).length > 0) return collected as StablecoinData[];

  const cacheKey = 'defi_stablecoins';
  const cached = cacheGet(cacheKey);
  if (cached) return cached as StablecoinData[];

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetchWithTimeout(`${STABLECOINS}/stablecoins?includePrices=true`);
    if (!res.ok) throw new Error(`DeFi Llama stables: ${res.status}`);
    const data = await res.json() as { peggedAssets?: Record<string, unknown>[] };

    const stables: StablecoinData[] = (data.peggedAssets || []).slice(0, 15).map((s: Record<string, unknown>): StablecoinData => ({
      name: s.name as string,
      symbol: s.symbol as string,
      pegType: s.pegType as string,
      circulating: (s.circulating as { peggedUSD?: number })?.peggedUSD || 0,
      price: (s.price || 1) as number,
    }));

    cacheSet(cacheKey, stables, 300000);
    return stables;
  } catch (err) {
    console.warn('[DeFiLlama stables]', (err as Error).message);
    return null;
  }
}

// Mock data fallback
export function getMockDefiData(): MockDefiData {
  return {
    protocols: [
      { name: 'Lido', symbol: 'LDO', tvl: 33200000000, change1d: 0.5, change7d: 2.1, category: 'Liquid Staking', chains: ['Ethereum'] },
      { name: 'Aave', symbol: 'AAVE', tvl: 12500000000, change1d: -0.3, change7d: 1.8, category: 'Lending', chains: ['Ethereum', 'Polygon', 'Avalanche'] },
      { name: 'MakerDAO', symbol: 'MKR', tvl: 8700000000, change1d: 0.1, change7d: -0.5, category: 'CDP', chains: ['Ethereum'] },
      { name: 'Uniswap', symbol: 'UNI', tvl: 5800000000, change1d: 1.2, change7d: 3.4, category: 'DEX', chains: ['Ethereum', 'Polygon', 'Arbitrum'] },
      { name: 'Curve', symbol: 'CRV', tvl: 4200000000, change1d: -0.8, change7d: -1.2, category: 'DEX', chains: ['Ethereum', 'Polygon'] },
      { name: 'Compound', symbol: 'COMP', tvl: 3100000000, change1d: 0.4, change7d: 0.9, category: 'Lending', chains: ['Ethereum'] },
      { name: 'Eigenlayer', symbol: 'EIGEN', tvl: 11200000000, change1d: 1.8, change7d: 5.2, category: 'Restaking', chains: ['Ethereum'] },
      { name: 'Rocket Pool', symbol: 'RPL', tvl: 3800000000, change1d: -0.2, change7d: 1.1, category: 'Liquid Staking', chains: ['Ethereum'] },
      { name: 'JustLend', symbol: 'JST', tvl: 6200000000, change1d: 0.6, change7d: -0.3, category: 'Lending', chains: ['Tron'] },
      { name: 'Pendle', symbol: 'PENDLE', tvl: 2900000000, change1d: 2.5, change7d: 8.1, category: 'Yield', chains: ['Ethereum', 'Arbitrum'] },
    ],
    chains: [
      { name: 'Ethereum', tvl: 62000000000 },
      { name: 'Tron', tvl: 8500000000 },
      { name: 'BSC', tvl: 5200000000 },
      { name: 'Solana', tvl: 4800000000 },
      { name: 'Arbitrum', tvl: 3200000000 },
      { name: 'Polygon', tvl: 1100000000 },
      { name: 'Avalanche', tvl: 950000000 },
      { name: 'Base', tvl: 1800000000 },
      { name: 'Optimism', tvl: 850000000 },
      { name: 'Sui', tvl: 600000000 },
    ],
  };
}
