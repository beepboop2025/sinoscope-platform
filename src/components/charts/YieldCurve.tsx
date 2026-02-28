import { memo, useRef, useEffect, type ReactElement } from 'react';
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';

interface YieldDataPoint {
  maturity: string;
  yield: number;
  [key: string]: unknown;
}

interface YieldCurveProps {
  data?: YieldDataPoint[];
  height?: number;
  prevData?: YieldDataPoint[];
}

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const YieldCurve = memo(({ data = [], height = 200, prevData }: YieldCurveProps): ReactElement | null => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const currentRef = useRef<ISeriesApi<'Line'> | null>(null);
  const prevRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const bg = getCSSVar('--bg-1') || '#0a0f1a';
    const text = getCSSVar('--text-3') || '#64748b';
    const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';
    const cyan = getCSSVar('--cyan') || '#06d6e0';

    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: { background: { color: bg }, textColor: text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
      grid: { vertLines: { color: border }, horzLines: { color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border },
    });

    const currentSeries = chart.addSeries(LineSeries, { color: cyan, lineWidth: 2 });
    currentRef.current = currentSeries;

    if (prevData) {
      const prevSeries = chart.addSeries(LineSeries, {
        color: getCSSVar('--text-4') || '#475569',
        lineWidth: 1,
        lineStyle: 2, // Dashed
      });
      prevRef.current = prevSeries;
    }

    chartRef.current = chart;

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
      currentRef.current = null;
      prevRef.current = null;
    };
  }, [height, !!prevData]);

  useEffect(() => {
    if (!currentRef.current || !data.length) return;

    const lwData = data.map((d, i) => ({ time: i as UTCTimestamp, value: d.yield }));
    currentRef.current.setData(lwData);

    if (prevRef.current && prevData) {
      const lwPrev = prevData.map((d, i) => ({ time: i as UTCTimestamp, value: d.yield }));
      prevRef.current.setData(lwPrev);
    }

    chartRef.current?.timeScale().fitContent();
  }, [data, prevData]);

  if (!data.length) return null;

  return <div ref={containerRef} style={{ width: '100%', height }} />;
});
YieldCurve.displayName = 'YieldCurve';
export default YieldCurve;
