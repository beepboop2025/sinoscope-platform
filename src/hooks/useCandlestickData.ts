import { useState, useEffect, useCallback } from 'react';
import { fetchFinnhubCandles } from '../services/api/stockApi';
import { cacheGet, cacheSet } from '../services/CacheManager';

interface Timeframe {
  readonly label: string;
  readonly resolution: string;
  readonly days: number;
}

interface CandleDataPoint {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface UseCandlestickDataReturn {
  data: CandleDataPoint[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  timeframes: readonly Timeframe[];
}

const TIMEFRAMES: readonly Timeframe[] = [
  { label: '1m', resolution: '1', days: 1 },
  { label: '5m', resolution: '5', days: 2 },
  { label: '15m', resolution: '15', days: 5 },
  { label: '1h', resolution: '60', days: 14 },
  { label: '4h', resolution: '240', days: 30 },
  { label: '1D', resolution: 'D', days: 365 },
];

export { TIMEFRAMES };

export function useCandlestickData(symbol: string, timeframeLabel: string = '1D'): UseCandlestickDataReturn {
  const [data, setData] = useState<CandleDataPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const tf = TIMEFRAMES.find(t => t.label === timeframeLabel) || TIMEFRAMES[5];

  const fetchData = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);

    const cacheKey = `candle_${symbol}_${tf.label}`;
    const cached = cacheGet<CandleDataPoint[]>(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      return;
    }

    try {
      const now = Math.floor(Date.now() / 1000);
      const from = now - tf.days * 86400;
      const candles = await fetchFinnhubCandles(symbol, tf.resolution, from, now);

      if (candles && candles.length > 0) {
        // Format for lightweight-charts: { time, open, high, low, close, volume }
        const formatted: CandleDataPoint[] = candles.map(c => ({
          time: tf.resolution === 'D'
            ? c.date // 'YYYY-MM-DD' string for daily
            : Math.floor(new Date(c.date).getTime() / 1000), // unix timestamp for intraday
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume || 0,
        }));
        cacheSet(cacheKey, formatted, tf.days <= 2 ? 30000 : 120000);
        setData(formatted);
      } else {
        // Generate mock candles when no API data available
        const mockCandles = generateMockCandles(symbol, tf);
        setData(mockCandles);
      }
    } catch (err: unknown) {
      setError((err as Error).message);
      // Fallback to mock data
      const mockCandles = generateMockCandles(symbol, tf);
      setData(mockCandles);
    }
    setLoading(false);
  }, [symbol, tf]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, error, refetch: fetchData, timeframes: TIMEFRAMES };
}

function generateMockCandles(symbol: string, tf: Timeframe): CandleDataPoint[] {
  const count = tf.resolution === 'D' ? tf.days : Math.min(tf.days * 24 * (60 / parseInt(tf.resolution || '1440')), 200);
  const basePrice = symbol.includes('BTC') ? 43000 : symbol.includes('ETH') ? 2500 : 185;
  const candles: CandleDataPoint[] = [];
  let price = basePrice;
  const now = Date.now();

  for (let i = count; i >= 0; i--) {
    const change = (Math.random() - 0.48) * basePrice * 0.02;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * basePrice * 0.005;
    const low = Math.min(open, close) - Math.random() * basePrice * 0.005;
    const vol = Math.floor(Math.random() * 1000000 + 500000);

    const intervalMs = tf.resolution === 'D' ? 86400000 : parseInt(tf.resolution) * 60000;
    const timestamp = now - i * intervalMs;

    candles.push({
      time: tf.resolution === 'D'
        ? new Date(timestamp).toISOString().split('T')[0]
        : Math.floor(timestamp / 1000),
      open: +(Number(open) || 0).toFixed(2),
      high: +(Number(high) || 0).toFixed(2),
      low: +(Number(low) || 0).toFixed(2),
      close: +(Number(close) || 0).toFixed(2),
      volume: vol,
    });
    price = close;
  }
  return candles;
}
