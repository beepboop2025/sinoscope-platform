import { useState, useEffect, useCallback, useRef, memo, type ReactElement, type MouseEvent } from 'react';
import { Newspaper, ExternalLink, Clock, AlertTriangle, RefreshCw } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchFinnhubNews } from '../../services/api/newsApi';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

interface Article {
  id?: string;
  url: string;
  title: string;
  source: string;
  time: number;
}

function generateMockArticles(): Article[] {
  const now = Date.now();
  return [
    { id: '1', url: '#', title: 'Bitcoin Surges Past $67K as Institutional Demand Accelerates', source: 'CoinDesk', time: now - 120_000 },
    { id: '2', url: '#', title: 'Fed Signals Potential Rate Cut in September Meeting', source: 'Reuters', time: now - 480_000 },
    { id: '3', url: '#', title: 'Ethereum Layer 2 TVL Hits All-Time High of $45B', source: 'The Block', time: now - 900_000 },
    { id: '4', url: '#', title: 'NVIDIA Maintains AI Chip Dominance Despite New Competition', source: 'CNBC', time: now - 1_800_000 },
    { id: '5', url: '#', title: 'Crude Oil Falls Below $70 on Demand Concerns', source: 'Financial Times', time: now - 3_600_000 },
    { id: '6', url: '#', title: 'Global Bond Yields Drop as Recession Fears Resurface', source: 'WSJ', time: now - 7_200_000 },
    { id: '7', url: '#', title: 'Apple Reports Mixed Q3 Earnings, iPhone Sales Decline 2%', source: 'Bloomberg', time: now - 10_800_000 },
    { id: '8', url: '#', title: 'Tesla Unveils Robotaxi Fleet Timeline, Shares Jump 5%', source: 'MarketWatch', time: now - 14_400_000 },
  ];
}

const PanelNews = memo((): ReactElement => {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState<boolean>(false);
  const inFlightRef = useRef<boolean>(false);

  const load = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFinnhubNews('general');
      if (data && data.length > 0) {
        setArticles(data as Article[]);
        setIsDemo(false);
      } else {
        // All sources returned nothing — use mock data
        setArticles(generateMockArticles());
        setIsDemo(true);
      }
    } catch (err: unknown) {
      console.warn('[PanelNews]', err);
      setError((err as Error).message || 'Failed to load news');
      // Fallback to mock on error
      setArticles(generateMockArticles());
      setIsDemo(true);
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 120000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && articles.length === 0) {
    return <PanelChrome title="News Feed" icon={Newspaper} iconColor="var(--cyan)"><PanelSkeleton /></PanelChrome>;
  }

  const timeAgo = (ts: number): string => {
    const mins = Math.round((Date.now() - ts) / 60000);
    if (mins < 60) return `${mins}m`;
    if (mins < 1440) return `${Math.round(mins / 60)}h`;
    return `${Math.round(mins / 1440)}d`;
  };

  return (
    <PanelChrome title={isDemo ? 'News Feed (Demo)' : 'News Feed'} icon={Newspaper} iconColor="var(--cyan)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {isDemo && (
          <div style={{ fontSize: 9, color: 'var(--amber)', background: 'rgba(245, 158, 11, 0.1)', padding: '3px 8px', borderRadius: 4, textAlign: 'center' }}>
            Demo Mode — Set API keys in .env for live news
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
            onMouseEnter={(e: MouseEvent<HTMLAnchorElement>) => e.currentTarget.style.borderColor = 'var(--border-2)'}
            onMouseLeave={(e: MouseEvent<HTMLAnchorElement>) => e.currentTarget.style.borderColor = 'var(--border-1)'}
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
