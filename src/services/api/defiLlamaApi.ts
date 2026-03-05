import { getCollectorData } from '../CollectorClient';

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

export async function fetchDefiProtocols(): Promise<DefiProtocol[] | null> {
  const collected = await getCollectorData('defi_protocols');
  if (collected && (collected as DefiProtocol[]).length > 0) return collected as DefiProtocol[];
  return null;
}

export async function fetchDefiTVL(): Promise<TVLDataPoint[] | null> {
  const collected = await getCollectorData('defi_tvl_history');
  if (collected && Array.isArray(collected) && collected.length > 0) return collected as TVLDataPoint[];
  return null;
}

export async function fetchChainTVL(): Promise<ChainTVL[] | null> {
  const collected = await getCollectorData('defi_chains');
  if (collected && (collected as ChainTVL[]).length > 0) return collected as ChainTVL[];
  return null;
}

export async function fetchDefiYields(): Promise<DefiYieldPool[] | null> {
  const collected = await getCollectorData('defi_yields');
  if (collected && (collected as DefiYieldPool[]).length > 0) return collected as DefiYieldPool[];
  return null;
}

export async function fetchStablecoins(): Promise<StablecoinData[] | null> {
  const collected = await getCollectorData('defi_stablecoins');
  if (collected && (collected as StablecoinData[]).length > 0) return collected as StablecoinData[];
  return null;
}
