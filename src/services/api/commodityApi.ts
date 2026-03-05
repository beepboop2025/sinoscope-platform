import { getCollectorData } from '../CollectorClient';
import { getCommodity as proxyCommodity } from '../BackendProxyClient';

interface CommodityObservation {
  date: string;
  value: number;
}

interface CommodityResult {
  price: number;
  date: string;
  history: CommodityObservation[];
}

// Map frontend commodity names to backend proxy names
const PROXY_NAME_MAP: Record<string, string> = {
  GASOLINE: 'gasoline',
  OIL_WTI: 'oil',
  NATGAS: 'gas',
  COPPER: 'copper',
};

export async function fetchCommodityPrice(commodity: string): Promise<CommodityObservation[] | null> {
  const collected = await getCollectorData('commodities');
  if (collected && typeof collected === 'object') {
    const commodities = collected as Record<string, unknown>;
    const entry = commodities[commodity];
    if (entry && Array.isArray(entry)) return entry as CommodityObservation[];
  }

  // On-demand fallback via backend proxy
  const proxyName = PROXY_NAME_MAP[commodity];
  if (proxyName) {
    const proxyData = await proxyCommodity(proxyName);
    if (proxyData && Array.isArray(proxyData)) {
      return (proxyData as { date: string; value: string }[])
        .filter((o) => o.value !== '.')
        .map((o) => ({ date: o.date, value: parseFloat(o.value) }));
    }
  }
  return null;
}

export async function fetchAllCommodities(): Promise<Record<string, CommodityResult>> {
  const collected = await getCollectorData('commodities');
  if (collected) return collected as Record<string, CommodityResult>;

  const names = Object.keys(PROXY_NAME_MAP);
  const results: Record<string, CommodityResult> = {};
  for (const name of names) {
    const data = await fetchCommodityPrice(name);
    if (data && data.length > 0) {
      results[name] = { price: data[0].value, date: data[0].date, history: data.slice(0, 10) };
    }
  }
  return results;
}
