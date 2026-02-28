import { memo, useState, useEffect, useCallback, type ReactElement, type ChangeEvent } from 'react';
import { Newspaper, ChevronDown, ChevronUp } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import { useSymbol } from '../../contexts/SymbolContext';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Sentiment = 'bullish' | 'bearish' | 'neutral';

interface NewsItem {
  id: number;
  headline: string;
  summary: string;
  source: string;
  publishedAt: number;
  sentiment: Sentiment;
  symbols: string[];
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function generateMockNews(): NewsItem[] {
  const now = Date.now();
  const items: NewsItem[] = [
    { id: 1, headline: 'Bitcoin Surges Past $67K as Institutional Demand Accelerates', summary: 'Major institutional investors including BlackRock and Fidelity report record inflows into Bitcoin ETFs, pushing prices to multi-month highs. Analysts project further upside as halving supply dynamics take effect.', source: 'CoinDesk', publishedAt: now - 120_000, sentiment: 'bullish', symbols: ['BTC', 'ETH'] },
    { id: 2, headline: 'Fed Signals Potential Rate Cut in September Meeting', summary: 'Federal Reserve Chair Jerome Powell indicated the central bank is closely monitoring inflation data and may consider easing monetary policy at the September FOMC meeting if current trends continue.', source: 'Reuters', publishedAt: now - 480_000, sentiment: 'bullish', symbols: ['SPY', 'QQQ', 'TLT'] },
    { id: 3, headline: 'Ethereum Layer 2 TVL Hits All-Time High of $45B', summary: 'Total value locked across Ethereum Layer 2 solutions including Arbitrum, Optimism, and Base reached a new record, signaling growing adoption of scaling solutions.', source: 'The Block', publishedAt: now - 900_000, sentiment: 'bullish', symbols: ['ETH', 'ARB', 'OP'] },
    { id: 4, headline: 'Apple Reports Mixed Q3 Earnings, iPhone Sales Decline 2%', summary: 'Apple Inc reported quarterly revenue of $85.8 billion, slightly beating estimates, but iPhone unit sales fell 2% year-over-year amid increased competition in China. Services revenue hit a new record.', source: 'Bloomberg', publishedAt: now - 1_800_000, sentiment: 'bearish', symbols: ['AAPL'] },
    { id: 5, headline: 'NVIDIA Maintains AI Chip Dominance Despite New Competition', summary: 'NVIDIA continues to hold over 80% market share in AI training chips. CEO Jensen Huang announced the next-generation Blackwell Ultra architecture during the keynote at GTC 2025.', source: 'CNBC', publishedAt: now - 3_600_000, sentiment: 'bullish', symbols: ['NVDA', 'AMD', 'INTC'] },
    { id: 6, headline: 'Crude Oil Falls Below $70 on Demand Concerns', summary: 'WTI crude oil prices dropped below $70 per barrel as weak economic data from China raised concerns about global demand. OPEC+ is expected to discuss potential production adjustments.', source: 'Financial Times', publishedAt: now - 5_400_000, sentiment: 'bearish', symbols: ['CL', 'XOM', 'CVX'] },
    { id: 7, headline: 'Solana DeFi Ecosystem Surpasses $8B in TVL', summary: 'The Solana blockchain has seen a resurgence in DeFi activity with total value locked exceeding $8 billion, driven by new protocols and improved network stability after recent upgrades.', source: 'Decrypt', publishedAt: now - 7_200_000, sentiment: 'bullish', symbols: ['SOL'] },
    { id: 8, headline: 'US Dollar Index Weakens on Dovish Fed Commentary', summary: 'The DXY dollar index fell 0.4% to 103.2 as multiple Fed governors hinted at a more accommodative stance. EUR/USD and GBP/USD both saw significant gains during the session.', source: 'Forex Live', publishedAt: now - 10_800_000, sentiment: 'bearish', symbols: ['DXY', 'EUR', 'GBP'] },
    { id: 9, headline: 'Tesla Unveils Robotaxi Fleet Timeline, Shares Jump 5%', summary: 'Tesla CEO Elon Musk provided an updated timeline for the commercial robotaxi service launch, now expected in select cities by Q2 2026. Shares rallied in after-hours trading on the news.', source: 'MarketWatch', publishedAt: now - 14_400_000, sentiment: 'bullish', symbols: ['TSLA'] },
    { id: 10, headline: 'Global Bond Yields Drop as Recession Fears Resurface', summary: 'Government bond yields across major economies fell sharply as investors sought safe-haven assets amid mixed economic data. The US 10-year yield dropped to 4.15%.', source: 'WSJ', publishedAt: now - 18_000_000, sentiment: 'bearish', symbols: ['TLT', 'AGG', 'BND'] },
    { id: 11, headline: 'Ripple Wins Partial Victory in SEC Lawsuit Appeal', summary: 'A federal appeals court upheld the lower court ruling that programmatic sales of XRP do not constitute securities. The decision has positive implications for the broader crypto industry.', source: 'CoinTelegraph', publishedAt: now - 21_600_000, sentiment: 'bullish', symbols: ['XRP'] },
    { id: 12, headline: 'Amazon Expands AWS AI Services with New Custom Chips', summary: 'Amazon Web Services announced its next-generation Trainium3 chips and expanded AI model hosting capabilities, intensifying competition with Microsoft Azure and Google Cloud.', source: 'TechCrunch', publishedAt: now - 28_800_000, sentiment: 'neutral', symbols: ['AMZN', 'MSFT', 'GOOG'] },
    { id: 13, headline: 'China PMI Data Misses Expectations for Third Month', summary: 'China\'s manufacturing PMI came in at 49.1, below the 50 threshold for the third consecutive month, raising concerns about the pace of economic recovery in the world\'s second-largest economy.', source: 'Nikkei Asia', publishedAt: now - 36_000_000, sentiment: 'bearish', symbols: ['FXI', 'KWEB', 'BABA'] },
    { id: 14, headline: 'MicroStrategy Adds Another 12,000 BTC to Holdings', summary: 'MicroStrategy announced the purchase of approximately 12,000 Bitcoin for $800 million, bringing its total holdings to over 226,000 BTC. The company funded the acquisition through a convertible note offering.', source: 'Bitcoin Magazine', publishedAt: now - 43_200_000, sentiment: 'bullish', symbols: ['BTC', 'MSTR'] },
    { id: 15, headline: 'European Markets Close Mixed Amid ECB Policy Uncertainty', summary: 'European equities ended the session with mixed results as investors digested conflicting signals from ECB officials regarding the timing of the next rate decision. The STOXX 600 finished flat.', source: 'Euronews', publishedAt: now - 50_400_000, sentiment: 'neutral', symbols: ['EWG', 'EWQ', 'FEZ'] },
  ];
  return items;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimeAgo(ts: number): string {
  const secs = Math.round((Date.now() - ts) / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

function sentimentColor(s: Sentiment): string {
  if (s === 'bullish') return 'var(--green)';
  if (s === 'bearish') return 'var(--red)';
  return 'var(--text-4)';
}

function sentimentBg(s: Sentiment): string {
  if (s === 'bullish') return 'rgba(34, 197, 94, 0.1)';
  if (s === 'bearish') return 'rgba(239, 68, 68, 0.1)';
  return 'rgba(148, 163, 184, 0.1)';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PanelNewsFeed = memo((): ReactElement => {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [filterInput, setFilterInput] = useState<string>('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { activeSymbol } = useSymbol();

  useEffect(() => {
    const timer = setTimeout(() => {
      setNews(generateMockNews());
      setLastUpdated(Date.now());
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const handleFilterChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setFilterInput(e.target.value);
  }, []);

  const toggleExpand = useCallback((id: number) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  // Determine effective filter: explicit input takes priority, else active symbol
  const effectiveFilter = filterInput.trim().toUpperCase() || activeSymbol?.toUpperCase() || '';

  const filteredNews = effectiveFilter
    ? news.filter((item) =>
        item.symbols.some((s) => s.toUpperCase().includes(effectiveFilter)) ||
        item.headline.toUpperCase().includes(effectiveFilter)
      )
    : news;

  if (loading) {
    return (
      <PanelChrome title="News Feed" icon={Newspaper} iconColor="var(--cyan)">
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="News Feed" icon={Newspaper} iconColor="var(--cyan)" lastUpdated={lastUpdated}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Filter input */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            type="text"
            value={filterInput}
            onChange={handleFilterChange}
            placeholder={`Filter by symbol (active: ${activeSymbol || 'none'})`}
            style={{
              flex: 1,
              padding: '4px 8px',
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
              background: 'var(--bg-1)',
              border: '1px solid var(--border-1)',
              borderRadius: 4,
              color: 'var(--text-1)',
              outline: 'none',
            }}
          />
          <span style={{ fontSize: 9, color: 'var(--text-4)', flexShrink: 0 }}>
            {filteredNews.length}/{news.length}
          </span>
        </div>

        {/* News list */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {filteredNews.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-4)', fontSize: 10 }}>
              No news matching "{effectiveFilter}"
            </div>
          )}

          {filteredNews.map((item) => {
            const isExpanded = expandedId === item.id;
            return (
              <div
                key={item.id}
                style={{
                  padding: '6px 4px',
                  borderBottom: '1px solid var(--border-1)',
                  cursor: 'pointer',
                }}
                onClick={() => toggleExpand(item.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggleExpand(item.id); }}
                aria-expanded={isExpanded}
              >
                {/* Headline row */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-1)', lineHeight: 1.4 }}>
                      {item.headline}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 9, color: 'var(--text-4)' }}>{item.source}</span>
                      <span style={{ fontSize: 9, color: 'var(--text-4)' }}>{formatTimeAgo(item.publishedAt)}</span>
                      <span style={{
                        fontSize: 8,
                        fontWeight: 600,
                        color: sentimentColor(item.sentiment),
                        background: sentimentBg(item.sentiment),
                        padding: '1px 6px',
                        borderRadius: 3,
                        textTransform: 'uppercase',
                        letterSpacing: 0.3,
                      }}>
                        {item.sentiment}
                      </span>
                    </div>
                    {/* Symbol tags */}
                    <div style={{ display: 'flex', gap: 3, marginTop: 3, flexWrap: 'wrap' }}>
                      {item.symbols.map((sym) => (
                        <span
                          key={sym}
                          style={{
                            fontSize: 8,
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--blue)',
                            background: 'rgba(59, 130, 246, 0.1)',
                            padding: '1px 5px',
                            borderRadius: 3,
                            fontWeight: 600,
                          }}
                        >
                          {sym}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div style={{ flexShrink: 0, marginTop: 2 }}>
                    {isExpanded ? <ChevronUp size={12} color="var(--text-4)" /> : <ChevronDown size={12} color="var(--text-4)" />}
                  </div>
                </div>

                {/* Expanded summary */}
                {isExpanded && (
                  <div style={{
                    marginTop: 6,
                    padding: '6px 8px',
                    background: 'var(--bg-1)',
                    borderRadius: 4,
                    fontSize: 10,
                    color: 'var(--text-3)',
                    lineHeight: 1.5,
                    borderLeft: `2px solid ${sentimentColor(item.sentiment)}`,
                  }}>
                    {item.summary}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{ fontSize: 9, color: 'var(--text-4)' }}>
          Mock data | {news.length} items
        </div>
      </div>
    </PanelChrome>
  );
});
PanelNewsFeed.displayName = 'PanelNewsFeed';
export default PanelNewsFeed;
