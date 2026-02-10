import { memo, useState, useEffect, useCallback, type ReactElement } from 'react';
import { BookOpen, RefreshCw, ExternalLink, Tag } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchAllFinanceResearch, getMockPapers } from '../../services/api/arxivApi';

interface Paper {
  id: string;
  title: string;
  authors?: string[];
  summary?: string;
  categories?: string[];
  published: string;
  url?: string;
  pdfUrl?: string;
}

const CAT_COLORS: Record<string, string> = {
  'q-fin.PM': 'var(--green)',
  'q-fin.ST': 'var(--blue)',
  'q-fin.TR': 'var(--orange)',
  'q-fin.MF': 'var(--purple)',
  'q-fin.CP': 'var(--cyan)',
  'q-fin.GN': 'var(--amber)',
  'q-fin.RM': 'var(--red)',
  'cs.AI': 'var(--teal)',
  'cs.LG': 'var(--green)',
  'cs.CL': 'var(--blue)',
};

const PanelResearchPapers = memo((): ReactElement => {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAllFinanceResearch();
      setPapers((data || getMockPapers()) as Paper[]);
    } catch {
      setPapers(getMockPapers() as Paper[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <PanelChrome title="Finance Research" icon={BookOpen} iconColor="var(--teal)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span style={{ fontSize: 9, color: 'var(--text-4)' }}>arXiv q-fin + ML papers</span>
          <button className="btn-ghost" onClick={loadData} disabled={loading} style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}>
            <RefreshCw size={9} /> Refresh
          </button>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {loading && papers.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 11 }}>Loading papers...</div>
          ) : (
            papers.map(p => (
              <div key={p.id} style={{ padding: '6px 4px', borderBottom: '1px solid var(--border-1)' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-1)', lineHeight: 1.3 }}>
                      {p.title}
                      {(p.url || p.pdfUrl) && (
                        <a href={p.pdfUrl || p.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-4)', marginLeft: 4 }}>
                          <ExternalLink size={9} />
                        </a>
                      )}
                    </div>
                    <div style={{ fontSize: 9, color: 'var(--text-3)', marginTop: 2 }}>
                      {p.authors?.join(', ')}
                    </div>
                    <div style={{ fontSize: 9, color: 'var(--text-4)', marginTop: 2, lineHeight: 1.3 }}>
                      {p.summary?.slice(0, 150)}{(p.summary?.length || 0) > 150 ? '...' : ''}
                    </div>
                    <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', marginTop: 3 }}>
                      {p.categories?.map(c => (
                        <span key={c} className="badge" style={{ background: 'var(--bg-3)', color: CAT_COLORS[c] || 'var(--text-4)', fontSize: 8, padding: '1px 4px' }}>
                          <Tag size={7} style={{ marginRight: 2 }} />{c}
                        </span>
                      ))}
                      <span style={{ fontSize: 8, color: 'var(--text-4)', marginLeft: 'auto' }}>{p.published}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{papers.length} papers · Source: arXiv (free)</div>
      </div>
    </PanelChrome>
  );
});
PanelResearchPapers.displayName = 'PanelResearchPapers';
export default PanelResearchPapers;
