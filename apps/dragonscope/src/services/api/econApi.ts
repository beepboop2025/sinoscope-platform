import { getCollectorData } from '../CollectorClient';
import { getEconIndicator as proxyEcon, getWorldBank as proxyWorldBank } from '../BackendProxyClient';

interface EconObservation {
  date: string;
  value: number;
}

// Map frontend indicator names to backend proxy names
const PROXY_INDICATOR_MAP: Record<string, string> = {
  GDP: 'gdp',
  CPI: 'cpi',
  UNEMPLOYMENT: 'unemployment',
  FED_RATE: 'fed_rate',
  RETAIL_SALES: 'retail_sales',
  HOUSING_STARTS: 'housing',
  M2: 'm2',
  TRADE_BALANCE: 'trade_balance',
};

export async function fetchEconIndicator(indicator: string): Promise<EconObservation[] | null> {
  // Collector-first: pre-fetched economic data keyed by indicator
  const collected = await getCollectorData('economic');
  if (collected && (collected as Record<string, unknown>)[indicator]) {
    return (collected as Record<string, EconObservation[]>)[indicator];
  }

  // On-demand fallback via backend proxy
  const proxyName = PROXY_INDICATOR_MAP[indicator];
  if (proxyName) {
    const proxyData = await proxyEcon(proxyName);
    if (proxyData && Array.isArray(proxyData)) {
      return (proxyData as { date: string; value: string }[])
        .filter((o) => o.value !== '.')
        .map((o) => ({ date: o.date, value: parseFloat(o.value) }));
    }
  }
  return null;
}

export async function fetchWorldBankIndicator(country: string = 'USA', indicator: string = 'NY.GDP.MKTP.KD.ZG'): Promise<EconObservation[] | null> {
  const proxyData = await proxyWorldBank(country, indicator);
  if (proxyData && Array.isArray(proxyData)) {
    return (proxyData as { date: string; value: number | null }[])
      .filter((e) => e.value != null)
      .map((e) => ({ date: e.date, value: e.value as number }));
  }
  return null;
}
