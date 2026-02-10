import { memo, useRef, useEffect, type ReactElement } from 'react';
import type { ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import { useChartTheme, getAccentColors } from './useChartTheme';
import { useChartInstance } from './useChartInstance';

interface DataPoint {
  time: string | number;
  value: number;
  color?: string;
}

interface LWBarChartProps {
  data: DataPoint[];
  color?: string;
  height?: number;
  showGrid?: boolean;
  colorByValue?: boolean;
}

const LWBarChart = memo(({ data, color, height = 250, showGrid = true, colorByValue = false }: LWBarChartProps): ReactElement => {
  const containerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const theme = useChartTheme();

  const chartRef = useChartInstance({
    containerRef,
    theme,
    extraOptions: {
      grid: {
        vertLines: { visible: showGrid },
        horzLines: { visible: showGrid },
      },
    },
  });

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || seriesRef.current) return;

    const colors = getAccentColors();
    const barColor = color || colors.cyan;

    const series = chart.addHistogramSeries({
      color: barColor,
    });
    seriesRef.current = series;

    return () => {
      seriesRef.current = null;
    };
  }, [chartRef.current, color]);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !data.length) return;

    const colors = getAccentColors();
    const lwData = data.map((d, i) => ({
      time: (typeof d.time === 'number' ? d.time : i) as UTCTimestamp,
      value: d.value,
      color: colorByValue
        ? (d.value >= 0 ? colors.green : colors.red)
        : d.color || undefined,
    }));

    series.setData(lwData);
    chart?.timeScale().fitContent();
  }, [data, colorByValue]);

  return <div ref={containerRef} style={{ width: '100%', height }} />;
});
LWBarChart.displayName = 'LWBarChart';
export default LWBarChart;
