import { memo, useState, useEffect, useCallback, type ReactElement } from 'react';
import { FileText, RefreshCw, ExternalLink } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchRecentFilings } from '../../services/api/secEdgarApi';

interface Filing {
  id: string;
  form: string;
  company: string;
  ticker?: string;
  url?: string;
  description?: string;
  filed: string;
}

const FORM_COLORS: Record<string, string> = {
  '10-K': 'var(--green)',
  '10-Q': 'var(--blue)',
  '8-K': 'var(--amber)',
  'S-1': 'var(--purple)',
  'DEF 14A': 'var(--cyan)',
};

const PanelSECFilings = memo((): ReactElement => {
  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [formFilter, setFormFilter] = useState<string>('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchRecentFilings();
      if (data) setFilings(data as Filing[]);
    } catch {
      /* no data available */
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const forms = [...new Set(filings.map(f => f.form))];
  const filtered = formFilter === 'all' ? filings : filings.filter(f => f.form === formFilter);

  return (
    <PanelChrome title="SEC Filings" icon={FileText} iconColor="var(--blue)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'center' }}>
          <button className={formFilter === 'all' ? 'btn-primary' : 'btn-ghost'} onClick={() => setFormFilter('all')} style={{ padding: '2px 7px', fontSize: 9 }}>All</button>
          {forms.map(f => (
            <button key={f} className={formFilter === f ? 'btn-primary' : 'btn-ghost'} onClick={() => setFormFilter(f)} style={{ padding: '2px 7px', fontSize: 9, color: FORM_COLORS[f] }}>
              {f}
            </button>
          ))}
          <button className="btn-ghost" onClick={loadData} disabled={loading} style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}>
            <RefreshCw size={9} />
          </button>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {filtered.map(f => (
            <div key={f.id} style={{ padding: '6px 4px', borderBottom: '1px solid var(--border-1)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="badge" style={{ background: 'var(--bg-3)', color: FORM_COLORS[f.form] || 'var(--text-3)', fontSize: 9, padding: '1px 5px', flexShrink: 0, fontWeight: 700 }}>
                  {f.form}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'JetBrains Mono, monospace' }}>
                  {f.ticker || f.company}
                </span>
                {f.url && (
                  <a href={f.url} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 'auto', color: 'var(--text-4)', flexShrink: 0 }}>
                    <ExternalLink size={10} />
                  </a>
                )}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2, lineHeight: 1.3 }}>
                {f.company}{f.ticker ? ` (${f.ticker})` : ''}
              </div>
              {f.description && (
                <div style={{ fontSize: 9, color: 'var(--text-4)', marginTop: 2 }}>{f.description}</div>
              )}
              <div style={{ fontSize: 9, color: 'var(--text-4)', marginTop: 2 }}>Filed: {f.filed}</div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-4)' }}>Source: SEC EDGAR (free)</div>
      </div>
    </PanelChrome>
  );
});
PanelSECFilings.displayName = 'PanelSECFilings';
export default PanelSECFilings;
