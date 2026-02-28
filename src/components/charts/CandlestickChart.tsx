import { memo, useRef, useEffect, type ReactElement } from 'react';
import { createChart, CandlestickSeries, LineSeries, type IChartApi, type ISeriesApi, type UTCTimestamp, type DeepPartial, type ChartOptions } from 'lightweight-charts';

interface CandlestickDataPoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  [key: string]: unknown;
}

interface OverlayConfig {
  key: string;
  name?: string;
  color?: string;
  width?: number;
  dash?: string;
}

interface CandlestickChartProps {
  data?: CandlestickDataPoint[];
  height?: number;
  overlays?: OverlayConfig[];
}

const OVERLAY_COLORS = ['#f59e0b', '#a78bfa', '#3b82f6', '#ec4899', '#14b8a6'];

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const CandlestickChart = memo(({ data = [], height = 300, overlays = [] }: CandlestickChartProps): ReactElement | null => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const overlayRefs = useRef<ISeriesApi<'Line'>[]>([]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const bg = getCSSVar('--bg-1') || '#0a0f1a';
    const text = getCSSVar('--text-3') || '#64748b';
    const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';
    const green = getCSSVar('--green') || '#00DC82';
    const red = getCSSVar('--red') || '#FF4458';

    const opts: DeepPartial<ChartOptions> = {
      width: container.clientWidth,
      height,
      layout: { background: { color: bg }, textColor: text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
      grid: { vertLines: { color: border }, horzLines: { color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border },
    };

    const chart = createChart(container, opts);
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: green,
      downColor: red,
      borderUpColor: green,
      borderDownColor: red,
      wickUpColor: green,
      wickDownColor: red,
    });
    candleRef.current = candleSeries;

    // Add overlay line series
    const oRefs: ISeriesApi<'Line'>[] = [];
    overlays.forEach((o, i) => {
      const lineSeries = chart.addSeries(LineSeries, {
        color: o.color || OVERLAY_COLORS[i % OVERLAY_COLORS.length],
        lineWidth: (o.width || 1) as 1 | 2 | 3 | 4,
      });
      oRefs.push(lineSeries);
    });
    overlayRefs.current = oRefs;

    const ro = new ResizeObserver(() => {
      if (container.clientWidth > 0) {
        chart.applyOptions({ width: container.clientWidth });
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      overlayRefs.current = [];
    };
  }, [height, overlays.length]);

  useEffect(() => {
    if (!candleRef.current || !data.length) return;

    const lwCandles = data.map((d, i) => ({
      time: i as UTCTimestamp,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    candleRef.current.setData(lwCandles);

    // Set overlay data
    overlays.forEach((o, i) => {
      const ref = overlayRefs.current[i];
      if (!ref) return;
      const lwData = data
        .map((d, idx) => ({ time: idx as UTCTimestamp, value: Number(d[o.key]) || 0 }))
        .filter(p => p.value !== 0);
      ref.setData(lwData);
    });

    chartRef.current?.timeScale().fitContent();
  }, [data, overlays]);

  if (!data.length) return null;

  return <div ref={containerRef} style={{ width: '100%', height }} />;
});
CandlestickChart.displayName = 'CandlestickChart';
export default CandlestickChart;
