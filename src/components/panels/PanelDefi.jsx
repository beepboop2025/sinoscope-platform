import { memo, useState, useEffect, useCallback } from 'react';
import { Layers, RefreshCw, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchDefiProtocols, fetchChainTVL, getMockDefiData } from '../../services/api/defiLlamaApi';

function formatTVL(n) {
  if (n >= 1e12) return '$' + (n / 1e12).toFixed(2) + 'T';
  if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  return '$' + n.toLocaleString();
}

const PanelDefi = memo(() => {
  const [protocols, setProtocols] = useState([]);
  const [chains, setChains] = useState([]);
  const [tab, setTab] = useState('protocols');
  const [loading, setLoading] = useState(true);
  const [partialError, setPartialError] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setPartialError(null);
    const mock = getMockDefiData();
    const [pResult, cResult] = await Promise.allSettled([fetchDefiProtocols(), fetchChainTVL()]);

    const pOk = pResult.status === 'fulfilled' && pResult.value;
    const cOk = cResult.status === 'fulfilled' && cResult.value;

    setProtocols(pOk ? pResult.value : mock.protocols);
    setChains(cOk ? cResult.value : mock.chains);

    if (!pOk && !cOk) {
      setPartialError('Both protocol and chain data failed to load — showing mock data');
    } else if (!pOk) {
      setPartialError('Protocol data unavailable — showing mock protocols');
    } else if (!cOk) {
      setPartialError('Chain data unavailable — showing mock chains');
    }

    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <PanelChrome title="DeFi TVL" icon={Layers} iconColor="var(--purple)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
          <button className={tab === 'protocols' ? 'btn-primary' : 'btn-ghost'} onClick={() => setTab('protocols')} style={{ padding: '2px 8px', fontSize: 9 }}>Protocols</button>
          <button className={tab === 'chains' ? 'btn-primary' : 'btn-ghost'} onClick={() => setTab('chains')} style={{ padding: '2px 8px', fontSize: 9 }}>Chains</button>
          <button className="btn-ghost" onClick={loadData} disabled={loading} style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}>
            <RefreshCw size={9} /> Refresh
          </button>
        </div>

        {partialError && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 8px', background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 4, fontSize: 9, color: 'var(--amber)' }}>
            <AlertTriangle size={10} />
            <span>{partialError}</span>
          </div>
        )}

        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {tab === 'protocols' && protocols.map((p, i) => (
            <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 4px', borderBottom: '1px solid var(--border-1)', fontSize: 10 }}>
              <span style={{ color: 'var(--text-4)', width: 16, textAlign: 'right', flexShrink: 0 }}>{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, color: 'var(--text-1)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>{p.name}</div>
                <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{p.category}{p.chains?.length > 0 ? ` · ${p.chains.slice(0, 2).join(', ')}` : ''}</div>
              </div>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'var(--text-1)' }}>{formatTVL(p.tvl)}</span>
              <span style={{ minWidth: 45, textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', color: (p.change1d || 0) >= 0 ? 'var(--green)' : 'var(--red)', display: 'flex', alignItems: 'center', gap: 2 }}>
                {(p.change1d || 0) >= 0 ? <TrendingUp size={9} /> : <TrendingDown size={9} />}
                {Math.abs(p.change1d || 0).toFixed(1)}%
              </span>
            </div>
          ))}

          {tab === 'chains' && chains.map((c, i) => {
            const maxTVL = chains[0]?.tvl || 1;
            const pct = (c.tvl / maxTVL) * 100;
            return (
              <div key={c.name} style={{ padding: '5px 4px', borderBottom: '1px solid var(--border-1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
                  <span style={{ color: 'var(--text-4)', width: 16, textAlign: 'right' }}>{i + 1}</span>
                  <span style={{ flex: 1, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>{c.name}</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-1)' }}>{formatTVL(c.tvl)}</span>
                </div>
                <div style={{ marginTop: 3, marginLeft: 22, height: 3, background: 'var(--bg-3)', borderRadius: 2 }}>
                  <div style={{ height: '100%', width: `${pct}%`, background: 'var(--purple)', borderRadius: 2 }} />
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-4)' }}>Source: DeFi Llama (free API)</div>
      </div>
    </PanelChrome>
  );
});
PanelDefi.displayName = 'PanelDefi';
export default PanelDefi;
