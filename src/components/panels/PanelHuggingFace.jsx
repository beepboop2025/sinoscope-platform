import { memo, useState, useEffect, useCallback } from 'react';
import { Brain, Download, Heart, RefreshCw, Tag, ExternalLink } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchFinanceModels, getMockHuggingFaceModels } from '../../services/api/huggingfaceApi';

const PIPELINE_COLORS = {
  'text-classification': 'var(--purple)',
  'text-generation': 'var(--cyan)',
  'token-classification': 'var(--blue)',
  'question-answering': 'var(--green)',
  'fill-mask': 'var(--amber)',
  'summarization': 'var(--teal)',
  'translation': 'var(--orange)',
  'unknown': 'var(--text-4)',
};

function formatDownloads(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

const PanelHuggingFace = memo(() => {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pipelineFilter, setPipelineFilter] = useState('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchFinanceModels();
      setModels(data || getMockHuggingFaceModels());
    } catch {
      setModels(getMockHuggingFaceModels());
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const pipelines = [...new Set(models.map(m => m.pipeline).filter(Boolean))];
  const filtered = pipelineFilter === 'all' ? models : models.filter(m => m.pipeline === pipelineFilter);

  return (
    <PanelChrome title="HuggingFace Finance" icon={Brain} iconColor="var(--amber)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Pipeline filter */}
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            className={pipelineFilter === 'all' ? 'btn-primary' : 'btn-ghost'}
            onClick={() => setPipelineFilter('all')}
            style={{ padding: '2px 7px', fontSize: 9 }}
          >All</button>
          {pipelines.map(p => (
            <button
              key={p}
              className={pipelineFilter === p ? 'btn-primary' : 'btn-ghost'}
              onClick={() => setPipelineFilter(p)}
              style={{ padding: '2px 7px', fontSize: 9, color: PIPELINE_COLORS[p] || undefined }}
            >{p}</button>
          ))}
          <button
            className="btn-ghost"
            onClick={loadData}
            disabled={loading}
            style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}
          >
            <RefreshCw size={9} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>

        {/* Model list */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {loading && models.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 11 }}>Loading models...</div>
          ) : (
            filtered.map(model => (
              <div key={model.id} style={{
                padding: '6px 8px', borderBottom: '1px solid var(--border-1)',
                display: 'flex', flexDirection: 'column', gap: 3,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Brain size={11} style={{ color: PIPELINE_COLORS[model.pipeline] || 'var(--text-3)', flexShrink: 0 }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--amber)', fontFamily: 'JetBrains Mono, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {model.name}
                  </span>
                  <a
                    href={`https://huggingface.co/${model.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ marginLeft: 'auto', color: 'var(--text-4)', flexShrink: 0 }}
                  >
                    <ExternalLink size={10} />
                  </a>
                </div>
                <div style={{ display: 'flex', gap: 8, fontSize: 9, color: 'var(--text-4)', alignItems: 'center' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 2, color: 'var(--green)' }}>
                    <Download size={9} /> {formatDownloads(model.downloads)}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 2, color: 'var(--red)' }}>
                    <Heart size={9} /> {model.likes}
                  </span>
                  <span className="badge" style={{
                    background: 'var(--bg-3)', fontSize: 8, padding: '1px 5px',
                    color: PIPELINE_COLORS[model.pipeline] || 'var(--text-3)',
                  }}>
                    {model.pipeline}
                  </span>
                  {model.library && (
                    <span style={{ color: 'var(--text-4)' }}>{model.library}</span>
                  )}
                </div>
                {model.tags.length > 0 && (
                  <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {model.tags.slice(0, 5).map(t => (
                      <span key={t} className="badge" style={{ background: 'var(--bg-3)', color: 'var(--teal)', fontSize: 8, padding: '1px 5px' }}>
                        <Tag size={7} style={{ marginRight: 2 }} />{t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-4)', padding: '2px 0' }}>
          {filtered.length} models · sorted by downloads
        </div>
      </div>
    </PanelChrome>
  );
});
PanelHuggingFace.displayName = 'PanelHuggingFace';
export default PanelHuggingFace;
