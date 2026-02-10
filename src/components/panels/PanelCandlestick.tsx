import { memo, useState, useEffect, useRef, useCallback, type ReactElement, type ChangeEvent } from 'react';
import { CandlestickChart as CandlestickIcon, RefreshCw } from 'lucide-react';
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import PanelChrome from '../shared/PanelChrome';
import { useCandlestickData, TIMEFRAMES } from '../../hooks/useCandlestickData';

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN', 'TSLA', 'META', 'AMD', 'NFLX', 'SPY'];

const PanelCandlestick = memo((): ReactElement => {
  const [symbol, setSymbol] = useState<string>('AAPL');
  const [timeframe, setTimeframe] = useState<string>('1D');
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const { data, loading, error, refetch } = useCandlestickData(symbol, timeframe);

  // Get CSS variable values for theming
  const getCSSVar = useCallback((name: string): string => {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }, []);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const container = chartContainerRef.current;
    const bgColor = getCSSVar('--bg-1') || '#0a0f1a';
    const textColor = getCSSVar('--text-3') || '#64748b';
    const borderColor = getCSSVar('--border-1') || '#1a2540';
    const gridColor = getCSSVar('--border-1') || '#1a2540';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { color: bgColor },
        textColor: textColor,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: gridColor },
        horzLines: { color: gridColor },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: getCSSVar('--cyan') || '#06d6e0', width: 1, style: 2 },
        horzLine: { color: getCSSVar('--cyan') || '#06d6e0', width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: borderColor,
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
      timeScale: {
        borderColor: borderColor,
        timeVisible: timeframe !== '1D',
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: getCSSVar('--green') || '#10b981',
      downColor: getCSSVar('--red') || '#ef4444',
      borderUpColor: getCSSVar('--green') || '#10b981',
      borderDownColor: getCSSVar('--red') || '#ef4444',
      wickUpColor: getCSSVar('--green') || '#10b981',
      wickDownColor: getCSSVar('--red') || '#ef4444',
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Handle resize
    const ro = new ResizeObserver(() => {
      if (container.clientWidth > 0 && container.clientHeight > 0) {
        chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [getCSSVar, timeframe]);

  // Update data when it changes
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !data.length) return;

    const greenColor = getCSSVar('--green') || '#10b981';
    const redColor = getCSSVar('--red') || '#ef4444';

    candleSeriesRef.current.setData(data);

    const volumeData = data.map((d: { time: unknown; volume: number; close: number; open: number }) => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open
        ? greenColor + '40'
        : redColor + '40',
    }));
    volumeSeriesRef.current.setData(volumeData);

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [data, getCSSVar]);

  // Calculate price info from data
  const lastCandle = data[data.length - 1] as { close: number; open: number } | undefined;
  const firstCandle = data[0] as { close: number; open: number } | undefined;
  const priceChange = lastCandle && firstCandle
    ? ((lastCandle.close - firstCandle.open) / firstCandle.open * 100)
    : 0;
  const isPositive = priceChange >= 0;

  return (
    <PanelChrome title={`${symbol} Candlestick`} icon={CandlestickIcon} iconColor="var(--amber)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Controls */}
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={symbol}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => setSymbol(e.target.value)}
            style={{
              background: 'var(--bg-2)', border: '1px solid var(--border-1)',
              borderRadius: 4, color: 'var(--text-1)', fontSize: 10,
              padding: '2px 4px', fontFamily: 'var(--font-mono)',
            }}
          >
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {TIMEFRAMES.map((tf: { label: string }) => (
            <button
              key={tf.label}
              className="btn-ghost"
              onClick={() => setTimeframe(tf.label)}
              style={{
                fontSize: 9, padding: '1px 5px',
                color: timeframe === tf.label ? 'var(--cyan)' : 'var(--text-3)',
                borderBottom: timeframe === tf.label ? '1px solid var(--cyan)' : 'none',
              }}
            >
              {tf.label}
            </button>
          ))}

          <button className="btn-ghost" onClick={refetch} style={{ fontSize: 9, padding: '1px 4px', marginLeft: 'auto' }}>
            <RefreshCw size={10} />
          </button>
        </div>

        {/* Price display */}
        {lastCandle && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>
              ${(Number(lastCandle.close) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span style={{ fontSize: 11, color: isPositive ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
              {isPositive ? '+' : ''}{(Number(priceChange) || 0).toFixed(2)}%
            </span>
            <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{timeframe}</span>
            {loading && <span style={{ fontSize: 9, color: 'var(--text-4)' }}>Loading...</span>}
          </div>
        )}

        {/* Chart container */}
        <div ref={chartContainerRef} style={{ flex: 1, minHeight: 150 }}>
          {error && data.length === 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '100%', color: 'var(--text-3)', fontSize: 11,
            }}>
              {error}
            </div>
          )}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelCandlestick.displayName = 'PanelCandlestick';
export default PanelCandlestick;
