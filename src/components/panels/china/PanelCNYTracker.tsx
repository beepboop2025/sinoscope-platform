import { useState, useEffect, useMemo, useRef, type ReactElement } from 'react';
import { ArrowLeftRight, AlertCircle } from 'lucide-react';
import { ChinaAPI } from '../../../services/api/chinaApi';
import { CNY_MARKET } from '../../../constants/china';
import { createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import PanelChrome from '../../shared/PanelChrome';

interface FXData { cnyUsd: number; cnhUsd: number; }
interface HistoryPoint { time: string; cny: number; cnh: number; spread: number; }

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export default function PanelCNYTracker(): ReactElement {
  const [fxData, setFxData] = useState<FXData | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const data = await ChinaAPI.fetchCNYCNHRates() as FXData | null;
        if (data) {
          setFxData(data);
          setHistory(prev => {
            const newPoint: HistoryPoint = {
              time: new Date().toLocaleTimeString(),
              cny: data.cnyUsd, cnh: data.cnhUsd,
              spread: (Number(data.cnhUsd) || 0) - (Number(data.cnyUsd) || 0),
            };
            return [...prev.slice(-49), newPoint];
          });
        }
      } catch (err) {
        console.warn('[PanelCNYTracker]', (err as Error).message);
      } finally { setLoading(false); }
    }
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  // Create chart
  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    const bg = getCSSVar('--bg-1') || '#0a0f1a';
    const text = getCSSVar('--text-3') || '#64748b';
    const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 150,
      layout: { background: { color: bg }, textColor: text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
      grid: { vertLines: { color: border }, horzLines: { color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border, visible: false },
    });

    const series = chart.addLineSeries({ lineWidth: 2 });
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

  // Update chart data
  useEffect(() => {
    if (!seriesRef.current || history.length <= 1) return;

    const green = getCSSVar('--green') || '#00DC82';
    const red = getCSSVar('--red') || '#FF4458';

    seriesRef.current.applyOptions({
      color: spread >= 0 ? red : green,
    });

    const lwData = history.map((d, i) => ({
      time: i as UTCTimestamp,
      value: d.spread,
    }));
    seriesRef.current.setData(lwData);
    chartRef.current?.timeScale().fitContent();
  }, [history]);

  const spread = useMemo(() => fxData ? fxData.cnhUsd - fxData.cnyUsd : 0, [fxData]);
  const spreadBps = useMemo(() => spread * 10000, [spread]);

  const getSpreadInterpretation = (): { text: string; color: string; level: string } => {
    if (spreadBps > 100) return { text: 'Offshore yuan weaker - capital outflow pressure', color: 'var(--red)', level: 'high' };
    if (spreadBps < -100) return { text: 'Offshore yuan stronger - inflow demand', color: 'var(--green)', level: 'high' };
    return { text: 'Normal spread range', color: 'var(--text-2)', level: 'normal' };
  };
  const interpretation = getSpreadInterpretation();

  if (loading && !fxData) {
    return (<PanelChrome title="CNY/CNH Tracker" icon={ArrowLeftRight} iconColor="var(--cyan)"><div style={{ color: 'var(--text-2)' }}>Loading FX data...</div></PanelChrome>);
  }

  const cnyMarket = CNY_MARKET as { onshore: { symbol: string; name: string; exchange: string }; offshore: { symbol: string; name: string; exchange: string }; spread: { description: string; normalRange: string } };

  return (
    <PanelChrome title="CNY/CNH Tracker" icon={ArrowLeftRight} iconColor="var(--cyan)">
      <div style={{ padding: 4 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--border-1)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>{cnyMarket.onshore.symbol} - {cnyMarket.onshore.name}</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{fxData?.cnyUsd?.toFixed(4) || 'N/A'}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>{cnyMarket.onshore.exchange}</div>
        </div>
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--border-1)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>{cnyMarket.offshore.symbol} - {cnyMarket.offshore.name}</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{fxData?.cnhUsd?.toFixed(4) || 'N/A'}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>{cnyMarket.offshore.exchange}</div>
        </div>
      </div>

      <div style={{ padding: 12, background: interpretation.level === 'high' ? 'var(--red-alpha)' : 'var(--surface-1)',
        borderRadius: 8, border: `1px solid ${interpretation.level === 'high' ? 'var(--red)' : 'var(--border-1)'}`, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          {Math.abs(spreadBps) > 50 ? <AlertCircle size={14} color={interpretation.color} /> : null}
          <span style={{ fontSize: 12, fontWeight: 500, color: interpretation.color }}>Spread: {spreadBps > 0 ? '+' : ''}{(Number(spreadBps) || 0).toFixed(0)} bps</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-2)' }}>{interpretation.text}</div>
      </div>

      {history.length > 1 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>Spread History (CNH - CNY)</div>
          <div ref={chartContainerRef} style={{ height: 150 }} />
        </div>
      )}

      <div style={{ marginTop: 12, padding: 10, background: 'var(--surface-1)', borderRadius: 6, fontSize: 11, color: 'var(--text-3)', lineHeight: 1.5 }}>
        <strong>CNY vs CNH:</strong> {cnyMarket.spread.description}<br />Normal range: {cnyMarket.spread.normalRange}
      </div>
      </div>
    </PanelChrome>
  );
}
