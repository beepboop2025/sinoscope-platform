import { memo, useRef, useEffect, type ReactElement } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type UTCTimestamp, type DeepPartial, type ChartOptions } from 'lightweight-charts';
import { CHART_COLORS } from '../../constants/colors';

interface BarConfig {
  key: string;
  name?: string;
  color?: string;
}

interface BarChartProps {
  data?: Record<string, unknown>[];
  bars?: BarConfig[];
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  xKey?: string;
  colorByValue?: boolean;
  formatY?: (value: number) => string;
  showBrush?: boolean;
}

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const BarChartComponent = memo(({ data = [], bars = [], height = 250, showGrid = true, colorByValue = false }: BarChartProps): ReactElement | null => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<ISeriesApi<'Histogram'>[]>([]);

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

    const refs: ISeriesApi<'Histogram'>[] = [];
    bars.forEach((b, i) => {
      const series = chart.addHistogramSeries({
        color: b.color || CHART_COLORS[i % CHART_COLORS.length],
      });
      refs.push(series);
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
  }, [height, showGrid, bars.length]);

  useEffect(() => {
    if (!seriesRefs.current.length || !data.length) return;

    const green = getCSSVar('--green') || '#00DC82';
    const red = getCSSVar('--red') || '#FF4458';

    bars.forEach((b, i) => {
      const ref = seriesRefs.current[i];
      if (!ref) return;

      const lwData = data.map((d, idx) => {
        const val = Number(d[b.key]) || 0;
        return {
          time: idx as UTCTimestamp,
          value: val,
          ...(colorByValue ? { color: val >= 0 ? green : red } : {}),
        };
      });
      ref.setData(lwData);
    });

    chartRef.current?.timeScale().fitContent();
  }, [data, bars, colorByValue]);

  if (!data.length) return null;

  return <div ref={containerRef} style={{ width: '100%', height }} />;
});
BarChartComponent.displayName = 'BarChartComponent';
export default BarChartComponent;
