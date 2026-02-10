import { useState, useEffect, useMemo, type ReactElement } from 'react';
import { ArrowLeftRight, AlertCircle } from 'lucide-react';
import { ChinaAPI } from '../../../services/api/chinaApi';
import { CNY_MARKET } from '../../../constants/china';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, ReferenceLine } from 'recharts';
import PanelChrome from '../../shared/PanelChrome';

interface FXData { cnyUsd: number; cnhUsd: number; }
interface HistoryPoint { time: string; cny: number; cnh: number; spread: number; }

export default function PanelCNYTracker(): ReactElement {
  const [fxData, setFxData] = useState<FXData | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

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
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--divider)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>{cnyMarket.onshore.symbol} - {cnyMarket.onshore.name}</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{fxData?.cnyUsd?.toFixed(4) || 'N/A'}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>{cnyMarket.onshore.exchange}</div>
        </div>
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--divider)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>{cnyMarket.offshore.symbol} - {cnyMarket.offshore.name}</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{fxData?.cnhUsd?.toFixed(4) || 'N/A'}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>{cnyMarket.offshore.exchange}</div>
        </div>
      </div>

      <div style={{ padding: 12, background: interpretation.level === 'high' ? 'var(--red-alpha)' : 'var(--surface-1)',
        borderRadius: 8, border: `1px solid ${interpretation.level === 'high' ? 'var(--red)' : 'var(--divider)'}`, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          {Math.abs(spreadBps) > 50 ? <AlertCircle size={14} color={interpretation.color} /> : null}
          <span style={{ fontSize: 12, fontWeight: 500, color: interpretation.color }}>Spread: {spreadBps > 0 ? '+' : ''}{(Number(spreadBps) || 0).toFixed(0)} bps</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-2)' }}>{interpretation.text}</div>
      </div>

      {history.length > 1 && (
        <div style={{ height: 150, marginTop: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>Spread History (CNH - CNY)</div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history}>
              <XAxis dataKey="time" hide />
              <YAxis domain={['auto', 'auto']} tickFormatter={(v: number) => `${(v * 10000).toFixed(0)}bps`} />
              <ReferenceLine y={0} stroke="var(--divider)" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="spread" stroke={spread >= 0 ? 'var(--red)' : 'var(--green)'} strokeWidth={2} dot={false} animationDuration={300} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ marginTop: 12, padding: 10, background: 'var(--surface-1)', borderRadius: 6, fontSize: 11, color: 'var(--text-3)', lineHeight: 1.5 }}>
        <strong>CNY vs CNH:</strong> {cnyMarket.spread.description}<br />Normal range: {cnyMarket.spread.normalRange}
      </div>
      </div>
    </PanelChrome>
  );
}
