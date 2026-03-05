import { memo, useState, useEffect, useCallback, type ReactElement } from 'react';
import { MessageCircle, RefreshCw, ArrowUp, ExternalLink } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchAllFinanceSubs, analyzeSentiment } from '../../services/api/redditApi';

interface RedditPost {
  id: string;
  title: string;
  subreddit: string;
  score: number;
  numComments: number;
  created: number;
  url?: string;
  flair?: string;
}

interface SentimentResult {
  bullish: number;
  neutral: number;
  bearish: number;
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

function formatScore(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

const SUB_COLORS: Record<string, string> = {
  wallstreetbets: '#ff4500',
  cryptocurrency: '#f7931a',
  stocks: '#3b82f6',
  investing: '#10b981',
  CryptoMarkets: '#a78bfa',
};

const PanelRedditSentiment = memo((): ReactElement => {
  const [posts, setPosts] = useState<RedditPost[]>([]);
  const [sentiment, setSentiment] = useState<SentimentResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [filter, setFilter] = useState<string>('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAllFinanceSubs();
      if (data) {
        const p = data as RedditPost[];
        setPosts(p);
        setSentiment(analyzeSentiment(p) as SentimentResult);
      }
    } catch {
      /* no data available */
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const subs = [...new Set(posts.map(p => p.subreddit))];
  const filtered = filter === 'all' ? posts : posts.filter(p => p.subreddit === filter);

  return (
    <PanelChrome title="Reddit Finance" icon={MessageCircle} iconColor="#ff4500">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Sentiment bar */}
        {sentiment && (
          <div style={{ display: 'flex', height: 14, borderRadius: 4, overflow: 'hidden', gap: 1 }}>
            <div style={{ width: `${sentiment.bullish}%`, background: 'var(--green)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: '#fff', fontWeight: 700, minWidth: sentiment.bullish > 5 ? 30 : 0 }}>
              {sentiment.bullish > 10 ? `Bull ${sentiment.bullish}%` : ''}
            </div>
            <div style={{ width: `${sentiment.neutral}%`, background: 'var(--bg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: 'var(--text-3)' }}>
              {sentiment.neutral > 10 ? `${sentiment.neutral}%` : ''}
            </div>
            <div style={{ width: `${sentiment.bearish}%`, background: 'var(--red)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: '#fff', fontWeight: 700, minWidth: sentiment.bearish > 5 ? 30 : 0 }}>
              {sentiment.bearish > 10 ? `Bear ${sentiment.bearish}%` : ''}
            </div>
          </div>
        )}

        {/* Subreddit filter */}
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'center' }}>
          <button className={filter === 'all' ? 'btn-primary' : 'btn-ghost'} onClick={() => setFilter('all')} style={{ padding: '2px 7px', fontSize: 9 }}>All</button>
          {subs.map(s => (
            <button key={s} className={filter === s ? 'btn-primary' : 'btn-ghost'} onClick={() => setFilter(s)} style={{ padding: '2px 7px', fontSize: 9 }}>
              <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', background: SUB_COLORS[s] || 'var(--text-4)', marginRight: 3 }} />
              r/{s}
            </button>
          ))}
          <button className="btn-ghost" onClick={loadData} disabled={loading} style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}>
            <RefreshCw size={9} />
          </button>
        </div>

        {/* Posts list */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {filtered.map(post => (
            <div key={post.id} style={{ padding: '5px 4px', borderBottom: '1px solid var(--border-1)' }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 28, gap: 1 }}>
                  <ArrowUp size={10} style={{ color: 'var(--orange)' }} />
                  <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--orange)', fontFamily: 'JetBrains Mono, monospace' }}>{formatScore(post.score)}</span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-1)', lineHeight: 1.3 }}>
                    {post.title}
                    {post.url && (
                      <a href={post.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-4)', marginLeft: 4 }}>
                        <ExternalLink size={9} />
                      </a>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 6, fontSize: 9, color: 'var(--text-4)', marginTop: 3 }}>
                    <span style={{ color: SUB_COLORS[post.subreddit] || 'var(--text-3)' }}>r/{post.subreddit}</span>
                    {post.flair && <span className="badge" style={{ background: 'var(--bg-3)', color: 'var(--text-3)', fontSize: 8, padding: '0px 4px' }}>{post.flair}</span>}
                    <span>{post.numComments} comments</span>
                    <span>{timeAgo(post.created)}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{filtered.length} posts · keyword sentiment</div>
      </div>
    </PanelChrome>
  );
});
PanelRedditSentiment.displayName = 'PanelRedditSentiment';
export default PanelRedditSentiment;
