import { useEffect, useRef, type RefObject } from 'react';
import { createChart, type IChartApi, type DeepPartial, type ChartOptions } from 'lightweight-charts';

interface UseChartInstanceOptions {
  containerRef: RefObject<HTMLDivElement | null>;
  theme: DeepPartial<ChartOptions>;
  extraOptions?: DeepPartial<ChartOptions>;
}

export function useChartInstance({ containerRef, theme, extraOptions }: UseChartInstanceOptions): RefObject<IChartApi | null> {
  const chartRef = useRef<IChartApi | null>(null);

  // Create and dispose chart
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      ...theme,
      ...extraOptions,
    });

    chartRef.current = chart;

    // ResizeObserver for responsive
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
    };
  }, [containerRef, theme, extraOptions]);

  // Sync theme changes
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions(theme);
    }
  }, [theme]);

  return chartRef;
}
