import { useState, useEffect, type ReactElement } from 'react';
import { Landmark, TrendingDown, TrendingUp, Clock, AlertCircle, History, Info } from 'lucide-react';
import { ChinaAPI } from '../../../services/api/chinaApi';
import { PBOC_TOOLS } from '../../../constants/china';
import PanelChrome from '../../shared/PanelChrome';

interface PBOCData {
  lendingFacility?: number; reverseRepo?: number; lpr1y?: number; lpr5y?: number; rrr?: number;
  source?: string; lastUpdated?: string;
}

interface RateAction { date: string; tool: string; rate: number; change: number; reason: string; }

const RATE_HISTORY: RateAction[] = [
  { date: '2024-02-20', tool: 'LPR_5Y', rate: 3.95, change: -25, reason: 'Support property sector' },
  { date: '2024-02-20', tool: 'LPR_1Y', rate: 3.45, change: -10, reason: 'Ease borrowing costs' },
  { date: '2023-09-15', tool: 'RRR', rate: 10.0, change: -25, reason: 'Boost liquidity' },
  { date: '2023-08-15', tool: 'MLF', rate: 2.50, change: -15, reason: 'Stimulate economy' },
  { date: '2023-08-15', tool: 'ReverseRepo', rate: 1.80, change: -10, reason: 'Policy easing' },
  { date: '2023-06-20', tool: 'LPR_1Y', rate: 3.55, change: -10, reason: 'Support growth' },
];

export default function PanelPBOCWatch(): ReactElement {
  const [pbocData, setPbocData] = useState<PBOCData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const data = await ChinaAPI.fetchPBOCRates() as PBOCData | null;
        if (data) setPbocData(data);
      } catch (err) {
        console.warn('[PanelPBOCWatch]', (err as Error).message);
      } finally { setLoading(false); }
    }
    fetchData();
    const interval = setInterval(fetchData, 300000);
    return () => clearInterval(interval);
  }, []);

  const pbocTools = PBOC_TOOLS as Record<string, { name: string; description: string }>;
  const tools = [
    { key: 'MLF', value: pbocData?.lendingFacility, tool: pbocTools.MLF },
    { key: 'ReverseRepo', value: pbocData?.reverseRepo, tool: pbocTools.ReverseRepo },
    { key: 'LPR_1Y', value: pbocData?.lpr1y, tool: pbocTools.LPR_1Y },
    { key: 'LPR_5Y', value: pbocData?.lpr5y, tool: pbocTools.LPR_5Y },
    { key: 'RRR', value: pbocData?.rrr, tool: pbocTools.RRR },
  ];

  if (loading) {
    return (<PanelChrome title="PBOC Watch" icon={Landmark} iconColor="var(--red)"><div style={{ color: 'var(--text-2)' }}>Loading PBOC data...</div></PanelChrome>);
  }

  return (
    <PanelChrome title="PBOC Watch" icon={Landmark} iconColor="var(--red)">
      <div style={{ padding: 4 }}>
      {pbocData?.source === 'static_reference' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <Info size={11} color="var(--text-3)" />
          <span style={{ fontSize: 10, color: 'var(--text-3)' }}>Reference data as of {pbocData.lastUpdated} — rates may have changed since</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: 20 }}>
        {tools.map(({ key, value, tool }) => (
          <div key={key} style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--divider)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 4, textTransform: 'uppercase' }}>{tool.name}</div>
            <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 2 }}>{value?.toFixed(2) || 'N/A'}%</div>
            <div style={{ fontSize: 10, color: 'var(--text-3)' }}>{tool.description}</div>
          </div>
        ))}
      </div>

      <div style={{ padding: 12, background: 'var(--surface-1)', borderRadius: 8, border: '1px solid var(--divider)', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}><AlertCircle size={14} color="var(--cyan)" /><span style={{ fontSize: 12, fontWeight: 500 }}>Current Policy Stance</span></div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{ padding: '4px 8px', background: 'var(--green-alpha)', color: 'var(--green)', borderRadius: 4, fontSize: 11, fontWeight: 500 }}>Easing</span>
          <span style={{ fontSize: 11, color: 'var(--text-2)' }}>Recent RRR cut and LPR reductions signal accommodative policy</span>
        </div>
      </div>

      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <History size={14} color="var(--text-2)" /><span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)' }}>Recent Policy Actions</span>
          <span style={{ padding: '2px 6px', fontSize: 9, borderRadius: 4, background: 'var(--surface-2)', color: 'var(--text-3)', fontWeight: 500 }}>Historical Reference</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {RATE_HISTORY.map((action, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: 'var(--surface-1)', borderRadius: 6, border: '1px solid var(--divider)' }}>
              <div style={{ minWidth: 80, fontSize: 11, color: 'var(--text-3)' }}>{action.date}</div>
              <div style={{ minWidth: 100 }}>
                <div style={{ fontSize: 12, fontWeight: 500 }}>{pbocTools[action.tool]?.name || action.tool}</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{action.rate}%</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: action.change < 0 ? 'var(--green)' : 'var(--red)', fontSize: 12, fontWeight: 500 }}>
                {action.change < 0 ? <TrendingDown size={12} /> : <TrendingUp size={12} />}{action.change > 0 ? '+' : ''}{action.change}bps
              </div>
              <div style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-3)', maxWidth: 150, textAlign: 'right' }}>{action.reason}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 16, padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px dashed var(--divider)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}><Clock size={12} color="var(--amber)" /><span style={{ fontSize: 11, fontWeight: 500 }}>Next LPR Fixing</span></div>
        <div style={{ fontSize: 12, color: 'var(--text-2)' }}>February 20, 2026 — 1-year and 5-year LPR rates announced monthly on the 20th</div>
      </div>
      </div>
    </PanelChrome>
  );
}
