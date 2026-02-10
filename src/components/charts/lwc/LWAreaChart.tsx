import { memo, useRef, useEffect, type ReactElement } from 'react';
import type { ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import { useChartTheme, getAccentColors } from './useChartTheme';
import { useChartInstance } from './useChartInstance';

interface DataPoint {
  time: string | number;
  value: number;
}

interface LWAreaChartProps {
  data: DataPoint[];
  color?: string;
  height?: number;
  showGrid?: boolean;
}

const LWAreaChart = memo(({ data, color, height = 250, showGrid = true }: LWAreaChartProps): ReactElement => {
  const containerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const theme = useChartTheme();

  const chartRef = useChartInstance({
    containerRef,
    theme,
    extraOptions: {
      grid: {
        vertLines: { visible: showGrid },
        horzLines: { visible: showGrid },
      },
      rightPriceScale: {
        scaleMargins: { top: 0.1, bottom: 0.05 },
      },
    },
  });

  // Create series once chart is ready
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || seriesRef.current) return;

    const colors = getAccentColors();
    const lineColor = color || colors.cyan;

    const series = chart.addAreaSeries({
      lineColor,
      topColor: lineColor + '40',
      bottomColor: lineColor + '05',
      lineWidth: 2,
    });
    seriesRef.current = series;

    return () => {
      seriesRef.current = null;
    };
  }, [chartRef.current, color]);

  // Update data
  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !data.length) return;

    // Convert data to lightweight-charts format
    const lwData = data.map((d, i) => ({
      time: (typeof d.time === 'number' ? d.time : i) as UTCTimestamp,
      value: d.value,
    }));

    series.setData(lwData);
    chart?.timeScale().fitContent();
  }, [data]);

  return <div ref={containerRef} style={{ width: '100%', height }} />;
});
LWAreaChart.displayName = 'LWAreaChart';
export default LWAreaChart;
