import { memo, useRef, useEffect, type ReactElement } from 'react';
import { CandlestickSeries, HistogramSeries, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import { useChartTheme, getAccentColors } from './useChartTheme';
import { useChartInstance } from './useChartInstance';

interface CandleData {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface LWCandlestickProps {
  data: CandleData[];
  height?: number;
  showVolume?: boolean;
}

const LWCandlestick = memo(({ data, height = 300, showVolume = true }: LWCandlestickProps): ReactElement => {
  const containerRef = useRef<HTMLDivElement>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const theme = useChartTheme();

  const chartRef = useChartInstance({
    containerRef,
    theme,
    extraOptions: {
      rightPriceScale: {
        scaleMargins: { top: 0.1, bottom: showVolume ? 0.25 : 0.05 },
      },
    },
  });

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || candleRef.current) return;

    const colors = getAccentColors();

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: colors.green,
      downColor: colors.red,
      borderUpColor: colors.green,
      borderDownColor: colors.red,
      wickUpColor: colors.green,
      wickDownColor: colors.red,
    });
    candleRef.current = candleSeries;

    if (showVolume) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: '',
      });
      volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeRef.current = volumeSeries;
    }

    return () => {
      candleRef.current = null;
      volumeRef.current = null;
    };
  }, [chartRef.current, showVolume]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!candleRef.current || !data.length) return;

    const colors = getAccentColors();

    candleRef.current.setData(data as Array<{ time: UTCTimestamp; open: number; high: number; low: number; close: number }>);

    if (volumeRef.current) {
      const volData = data.map(d => ({
        time: d.time as UTCTimestamp,
        value: d.volume || 0,
        color: d.close >= d.open ? colors.green + '40' : colors.red + '40',
      }));
      volumeRef.current.setData(volData);
    }

    chart?.timeScale().fitContent();
  }, [data]);

  return <div ref={containerRef} style={{ width: '100%', height }} />;
});
LWCandlestick.displayName = 'LWCandlestick';
export default LWCandlestick;
