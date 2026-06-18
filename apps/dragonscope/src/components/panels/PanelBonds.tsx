import { memo, useRef, useEffect, type ReactElement } from 'react';
import { Landmark } from 'lucide-react';
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import type { BondYield } from '../../types/market';

interface PanelBondsProps {
  data?: BondYield[];
}

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const PanelBonds = memo(({ data }: PanelBondsProps): ReactElement => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    const bg = getCSSVar('--bg-1') || '#0a0f1a';
    const text = getCSSVar('--text-3') || '#64748b';
    const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';
    const purple = getCSSVar('--purple') || '#8B5CF6';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 160,
      layout: { background: { color: bg }, textColor: text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
      grid: { vertLines: { color: border }, horzLines: { color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border },
    });

    const series = chart.addSeries(LineSeries, {
      color: purple,
      lineWidth: 2,
    });
    chartRef.current = chart;
    seriesRef.current = series;

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
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !data?.length) return;

    const lwData = data.map((d, i) => ({
      time: i as UTCTimestamp,
      value: Number(d.yield) || 0,
    }));
    seriesRef.current.setData(lwData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  if (!data || data.length === 0) {
    return <PanelChrome title="US Treasury Yields" icon={Landmark} iconColor="var(--purple)"><PanelSkeleton /></PanelChrome>;
  }

  return (
    <PanelChrome title="US Treasury Yields" icon={Landmark} iconColor="var(--purple)">
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {data.map(d => (
          <div key={d.maturity} style={{ background: 'var(--surface-2)', borderRadius: 6, padding: '6px 10px', border: '1px solid var(--border-1)', minWidth: 60, textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase' }}>{d.maturity}</div>
            <div className="mono" style={{ fontSize: 14, fontWeight: 600, color: 'var(--purple)' }}>
              {(Number(d.yield) || 0).toFixed(2)}%
            </div>
          </div>
        ))}
      </div>
      <div ref={chartContainerRef} style={{ height: 160 }} />
    </PanelChrome>
  );
});
PanelBonds.displayName = "PanelBonds";
export default PanelBonds;
