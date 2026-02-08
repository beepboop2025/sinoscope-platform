import { useState, useEffect, useCallback, memo } from 'react';
import { Newspaper, ExternalLink, Clock, AlertTriangle, RefreshCw } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchFinnhubNews } from '../../services/api/newsApi';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

const PanelNews = memo(() => {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFinnhubNews('general');
      if (data) setArticles(data);
    } catch (err) {
      console.warn('[PanelNews]', err);
      setError(err.message || 'Failed to load news');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 120000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && articles.length === 0) {
    return <PanelChrome title="News Feed" icon={Newspaper} iconColor="var(--cyan)"><PanelSkeleton /></PanelChrome>;
  }

  const timeAgo = (ts) => {
    const mins = Math.round((Date.now() - ts) / 60000);
    if (mins < 60) return `${mins}m`;
    if (mins < 1440) return `${Math.round(mins / 60)}h`;
    return `${Math.round(mins / 1440)}d`;
  };

  return (
    <PanelChrome title="News Feed" icon={Newspaper} iconColor="var(--cyan)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {error && articles.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, gap: 8, color: 'var(--text-3)' }}>
            <AlertTriangle size={20} color="var(--amber)" />
            <span style={{ fontSize: 11, textAlign: 'center' }}>{error}</span>
            <button className="btn-ghost" onClick={load} style={{ fontSize: 10, padding: '3px 10px', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={10} /> Retry
            </button>
          </div>
        ) : articles.length === 0 && !loading && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 11, lineHeight: 1.6 }}>
            No news available. Set any of these env vars for live news:<br/>
            VITE_FINNHUB_API_KEY, VITE_NEWSDATA_API_KEY,<br/>
            VITE_NEWSAPI_API_KEY, VITE_WORLD_NEWS_API_KEY
          </div>
        )}
        {articles.map(a => (
          <a
            key={a.id || a.url}
            href={a.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'block',
              padding: '8px 10px',
              background: 'var(--bg-1)',
              borderRadius: 6,
              border: '1px solid var(--border-1)',
              textDecoration: 'none',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-2)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-1)'}
          >
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-1)', marginBottom: 4, lineHeight: 1.3 }}>
              {a.title}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'var(--text-4)' }}>
              <span>{a.source}</span>
              <Clock size={10} />
              <span>{timeAgo(a.time)}</span>
              <ExternalLink size={10} style={{ marginLeft: 'auto' }} />
            </div>
          </a>
        ))}
      </div>
    </PanelChrome>
  );
});
PanelNews.displayName = "PanelNews";
export default PanelNews;
