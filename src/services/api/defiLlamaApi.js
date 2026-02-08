import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';

// DeFi Llama is free, no API key needed, generous limits
createRateLimiter('defillama', 20, 60000);

const BASE = 'https://api.llama.fi';
const YIELDS = 'https://yields.llama.fi';
const STABLECOINS = 'https://stablecoins.llama.fi';

// Top DeFi protocols by TVL
export async function fetchDefiProtocols() {
  const cacheKey = 'defi_protocols';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetch(`${BASE}/protocols`);
    if (!res.ok) throw new Error(`DeFi Llama protocols: ${res.status}`);
    const data = await res.json();

    const protocols = (data || []).slice(0, 50).map(p => ({
      name: p.name,
      symbol: p.symbol || '',
      tvl: p.tvl || 0,
      change1h: p.change_1h || 0,
      change1d: p.change_1d || 0,
      change7d: p.change_7d || 0,
      category: p.category || '',
      chains: (p.chains || []).slice(0, 5),
      url: p.url || '',
      logo: p.logo || '',
    }));

    cacheSet(cacheKey, protocols, 300000);
    return protocols;
  } catch (err) {
    console.warn('[DeFiLlama protocols]', err.message);
    return null;
  }
}

// Total TVL across all chains
export async function fetchDefiTVL() {
  const cacheKey = 'defi_tvl_total';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetch(`${BASE}/v2/historicalChainTvl`);
    if (!res.ok) throw new Error(`DeFi Llama TVL: ${res.status}`);
    const data = await res.json();
    const recent = (data || []).slice(-30).map(d => ({
      date: new Date(d.date * 1000).toISOString().split('T')[0],
      tvl: d.tvl,
    }));
    cacheSet(cacheKey, recent, 300000);
    return recent;
  } catch (err) {
    console.warn('[DeFiLlama TVL]', err.message);
    return null;
  }
}

// Chain TVL breakdown
export async function fetchChainTVL() {
  const cacheKey = 'defi_chain_tvl';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetch(`${BASE}/v2/chains`);
    if (!res.ok) throw new Error(`DeFi Llama chains: ${res.status}`);
    const data = await res.json();

    const chains = (data || []).slice(0, 20).map(c => ({
      name: c.name,
      tvl: c.tvl || 0,
      tokenSymbol: c.tokenSymbol || '',
      gecko_id: c.gecko_id || '',
    }));

    cacheSet(cacheKey, chains, 300000);
    return chains;
  } catch (err) {
    console.warn('[DeFiLlama chains]', err.message);
    return null;
  }
}

// Top DeFi yields
export async function fetchDefiYields() {
  const cacheKey = 'defi_yields';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetch(`${YIELDS}/pools`);
    if (!res.ok) throw new Error(`DeFi Llama yields: ${res.status}`);
    const data = await res.json();

    // Filter for reasonable yields with meaningful TVL
    const pools = (data.data || [])
      .filter(p => p.tvlUsd > 1000000 && p.apy > 0 && p.apy < 100)
      .sort((a, b) => b.tvlUsd - a.tvlUsd)
      .slice(0, 40)
      .map(p => ({
        pool: p.pool,
        project: p.project,
        symbol: p.symbol,
        chain: p.chain,
        tvl: p.tvlUsd,
        apy: p.apy,
        apyBase: p.apyBase || 0,
        apyReward: p.apyReward || 0,
        stablecoin: p.stablecoin || false,
      }));

    cacheSet(cacheKey, pools, 300000);
    return pools;
  } catch (err) {
    console.warn('[DeFiLlama yields]', err.message);
    return null;
  }
}

// Stablecoin market caps
export async function fetchStablecoins() {
  const cacheKey = 'defi_stablecoins';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('defillama')) return null;
  consumeToken('defillama');

  try {
    const res = await fetch(`${STABLECOINS}/stablecoins?includePrices=true`);
    if (!res.ok) throw new Error(`DeFi Llama stables: ${res.status}`);
    const data = await res.json();

    const stables = (data.peggedAssets || []).slice(0, 15).map(s => ({
      name: s.name,
      symbol: s.symbol,
      pegType: s.pegType,
      circulating: s.circulating?.peggedUSD || 0,
      price: s.price || 1,
    }));

    cacheSet(cacheKey, stables, 300000);
    return stables;
  } catch (err) {
    console.warn('[DeFiLlama stables]', err.message);
    return null;
  }
}

// Mock data fallback
export function getMockDefiData() {
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
