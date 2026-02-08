import { memo, useState, useEffect, useCallback } from 'react';
import { Github, Star, GitFork, ExternalLink, RefreshCw, Code } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchGithubFinanceRepos, getMockGithubRepos } from '../../services/api/githubApi';

const LANG_COLORS = {
  Python: '#3572A5',
  JavaScript: '#f1e05a',
  TypeScript: '#3178c6',
  'C#': '#178600',
  'C++': '#f34b7d',
  Rust: '#dea584',
  Go: '#00ADD8',
  Java: '#b07219',
  'Jupyter Notebook': '#DA5B0B',
  R: '#198CE7',
};

function formatNum(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'today';
  if (days === 1) return '1d ago';
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

const PanelGithubTrending = memo(() => {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchGithubFinanceRepos();
      setRepos(data || getMockGithubRepos());
    } catch {
      setRepos(getMockGithubRepos());
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const languages = [...new Set(repos.map(r => r.language).filter(Boolean))].slice(0, 6);
  const filtered = filter === 'all' ? repos : repos.filter(r => r.language === filter);

  return (
    <PanelChrome title="GitHub Finance" icon={Github} iconColor="var(--text-1)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Filter bar */}
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            className={filter === 'all' ? 'btn-primary' : 'btn-ghost'}
            onClick={() => setFilter('all')}
            style={{ padding: '2px 7px', fontSize: 9 }}
          >All</button>
          {languages.map(lang => (
            <button
              key={lang}
              className={filter === lang ? 'btn-primary' : 'btn-ghost'}
              onClick={() => setFilter(lang)}
              style={{ padding: '2px 7px', fontSize: 9 }}
            >
              <span style={{
                display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                background: LANG_COLORS[lang] || 'var(--text-4)', marginRight: 3,
              }} />
              {lang}
            </button>
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

        {/* Repo list */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {loading && repos.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 11 }}>Loading repos...</div>
          ) : (
            filtered.map(repo => (
              <div key={repo.id} style={{
                padding: '6px 8px', borderBottom: '1px solid var(--border-1)',
                display: 'flex', flexDirection: 'column', gap: 3,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Code size={11} style={{ color: LANG_COLORS[repo.language] || 'var(--text-3)', flexShrink: 0 }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {repo.name}
                  </span>
                  {repo.url && (
                    <a href={repo.url} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 'auto', color: 'var(--text-4)', flexShrink: 0 }}>
                      <ExternalLink size={10} />
                    </a>
                  )}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-3)', lineHeight: 1.3 }}>
                  {repo.description}
                </div>
                <div style={{ display: 'flex', gap: 8, fontSize: 9, color: 'var(--text-4)', alignItems: 'center' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 2, color: 'var(--yellow)' }}>
                    <Star size={9} /> {formatNum(repo.stars)}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <GitFork size={9} /> {formatNum(repo.forks)}
                  </span>
                  <span style={{
                    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                    background: LANG_COLORS[repo.language] || 'var(--text-4)',
                  }} />
                  <span>{repo.language}</span>
                  {repo.license && <span style={{ color: 'var(--text-4)' }}>{repo.license}</span>}
                  <span style={{ marginLeft: 'auto' }}>{timeAgo(repo.updated)}</span>
                </div>
                {repo.topics.length > 0 && (
                  <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {repo.topics.map(t => (
                      <span key={t} className="badge" style={{ background: 'var(--bg-3)', color: 'var(--purple)', fontSize: 8, padding: '1px 5px' }}>
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-4)', padding: '2px 0' }}>
          {filtered.length} repos · sorted by stars
        </div>
      </div>
    </PanelChrome>
  );
});
PanelGithubTrending.displayName = 'PanelGithubTrending';
export default PanelGithubTrending;
