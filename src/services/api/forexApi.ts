import { getCollectorData } from '../CollectorClient';
import type { ForexRates, ForexTimeseries } from '../../types';

export async function fetchForexRates(base: string = 'USD'): Promise<ForexRates | null> {
  const collected = await getCollectorData('forex');
  if (collected) return collected as ForexRates;
  return null;
}

export async function fetchForexTimeseries(base: string = 'USD', symbols: string = 'CNY,EUR,GBP,JPY', days: number = 30): Promise<ForexTimeseries | null> {
  const collected = await getCollectorData('forex_timeseries');
  if (collected) return collected as ForexTimeseries;
  return null;
}
