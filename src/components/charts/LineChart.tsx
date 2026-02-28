import { memo, useRef, useEffect, type ReactElement } from 'react';
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type UTCTimestamp, type DeepPartial, type ChartOptions } from 'lightweight-charts';
import { CHART_COLORS } from '../../constants/colors';

interface SeriesConfig {
  key: string;
  name?: string;
  color?: string;
  width?: number;
}

interface LineChartProps {
  data?: Record<string, unknown>[];
  series?: SeriesConfig[];
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  xKey?: string;
  yDomain?: [number | string, number | string];
  formatY?: (value: number) => string;
  showBrush?: boolean;
}

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const LineChartComponent = memo(({ data = [], series = [], height = 250, showGrid = true, xKey = 'time' }: LineChartProps): ReactElement | null => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<ISeriesApi<'Line'>[]>([]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const bg = getCSSVar('--bg-1') || '#0a0f1a';
    const text = getCSSVar('--text-3') || '#64748b';
    const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';

    const opts: DeepPartial<ChartOptions> = {
      width: container.clientWidth,
      height,
      layout: { background: { color: bg }, textColor: text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
      grid: { vertLines: { visible: showGrid, color: border }, horzLines: { visible: showGrid, color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border },
    };

    const chart = createChart(container, opts);
    chartRef.current = chart;

    // Add series
    const refs: ISeriesApi<'Line'>[] = [];
    series.forEach((s, i) => {
      const lineSeries = chart.addSeries(LineSeries, {
        color: s.color || CHART_COLORS[i % CHART_COLORS.length],
        lineWidth: (s.width || 1.5) as 1 | 2 | 3 | 4,
      });
      refs.push(lineSeries);
    });
    seriesRefs.current = refs;

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
      seriesRefs.current = [];
    };
  }, [height, showGrid, series.length]);

  // Update data
  useEffect(() => {
    if (!seriesRefs.current.length || !data.length) return;

    series.forEach((s, i) => {
      const ref = seriesRefs.current[i];
      if (!ref) return;

      const lwData = data.map((d, idx) => ({
        time: idx as UTCTimestamp,
        value: Number(d[s.key]) || 0,
      }));
      ref.setData(lwData);
    });

    chartRef.current?.timeScale().fitContent();
  }, [data, series]);

  if (!data.length) return null;

  return <div ref={containerRef} style={{ width: '100%', height }} />;
});
LineChartComponent.displayName = 'LineChartComponent';
export default LineChartComponent;
