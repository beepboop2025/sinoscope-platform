import { getCollectorData } from '../CollectorClient';
import { getYield as proxyYield } from '../BackendProxyClient';

interface FREDObservation {
  date: string;
  value: number;
}

interface YieldCurvePoint {
  maturity: string;
  yield: number;
  date: string;
}

export async function fetchTreasuryYield(maturity: string = '10Y'): Promise<FREDObservation[] | null> {
  // Collector-first: backend pre-fetches bond data keyed by maturity
  const collected = await getCollectorData('bonds');
  if (collected && typeof collected === 'object') {
    const bonds = collected as Record<string, unknown>;
    const entry = bonds[maturity];
    if (entry && Array.isArray(entry)) return entry as FREDObservation[];
  }

  // On-demand fallback via backend proxy
  const proxyData = await proxyYield(maturity.toLowerCase());
  if (proxyData && Array.isArray(proxyData)) {
    return (proxyData as { date: string; value: string }[])
      .filter((o) => o.value !== '.')
      .map((o) => ({ date: o.date, value: parseFloat(o.value) }));
  }
  return null;
}

export async function fetchYieldCurve(): Promise<YieldCurvePoint[] | null> {
  const collected = await getCollectorData('yield_curve');
  if (collected) return collected as YieldCurvePoint[];

  // Build yield curve from individual maturities
  const maturities = ['1M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y'];
  const results: YieldCurvePoint[] = [];
  for (const mat of maturities) {
    const data = await fetchTreasuryYield(mat);
    if (data && data.length > 0) {
      results.push({ maturity: mat, yield: data[0].value, date: data[0].date });
    }
  }
  return results.length > 0 ? results : null;
}
