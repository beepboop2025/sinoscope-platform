import React, { useEffect, useState, useRef } from 'react';
import { 
  Newspaper, 
  Search, 
  Filter, 
  Clock, 
  TrendingUp, 
  TrendingDown,
  Minus,
  ExternalLink,
  Bookmark,
  Share2,
  Bell,
  Settings,
  MoreHorizontal,
  ChevronDown,
  ChevronUp,
  Hash,
  BarChart3,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Download,
  X,
} from 'lucide-react';
import { useNewsStore, useTerminalStore } from '../stores/terminalStore';
import { formatNumber, formatPrice, tw } from '../utils/styles';

// Mock news sources
const NEWS_SOURCES = [
  { id: 'bloomberg', name: 'Bloomberg', color: '#2800D7' },
  { id: 'reuters', name: 'Reuters', color: '#FF8000' },
  { id: 'cnbc', name: 'CNBC', color: '#005594' },
  { id: 'wsj', name: 'WSJ', color: '#000000' },
  { id: 'ft', name: 'Financial Times', color: '#FFF1E5' },
  { id: 'seekingalpha', name: 'Seeking Alpha', color: '#FF6600' },
];

// Mock sectors
const SECTORS = [
  'Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer', 'Industrial', 'Materials', 'Utilities'
];

// Generate mock news article
const generateNewsArticle = () => {
  const sources = NEWS_SOURCES.map(s => s.id);
  const sentiments = ['positive', 'negative', 'neutral'];
  const categories = ['earnings', 'mergers', 'market', 'economy', 'policy', 'tech'];
  
  const templates = [
    { headline: '{SYMBOL} Reports Q{QUARTER} Earnings: EPS Beats by ${BEAT}', category: 'earnings', sentiment: 'positive' },
    { headline: '{SYMBOL} Announces Acquisition of {TARGET} for ${AMOUNT}B', category: 'mergers', sentiment: 'positive' },
    { headline: 'Fed Signals {DIRECTION} Interest Rate Policy', category: 'policy', sentiment: 'neutral' },
    { headline: '{SECTOR} Stocks Rally on Strong {METRIC} Data', category: 'market', sentiment: 'positive' },
    { headline: '{SYMBOL} Issues {DIRECTION} Guidance for FY{YEAR}', category: 'earnings', sentiment: 'neutral' },
    { headline: 'Breaking: {SYMBOL} {EVENT}', category: 'market', sentiment: 'negative' },
    { headline: 'Analyst {ACTION} {SYMBOL} Price Target to ${TARGET}', category: 'market', sentiment: 'positive' },
    { headline: '{SYMBOL} Expands Operations in {REGION}', category: 'market', sentiment: 'positive' },
  ];
  
  const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX', 'AMD', 'INTC', 'SPY', 'QQQ'];
  const template = templates[Math.floor(Math.random() * templates.length)];
  const symbol = symbols[Math.floor(Math.random() * symbols.length)];
  
  const variables = {
    SYMBOL: symbol,
    QUARTER: Math.floor(Math.random() * 4) + 1,
    BEAT: (Math.random() * 0.5).toFixed(2),
    TARGET: ['TechCorp', 'DataSystems', 'CloudNine', 'NextGen Solutions'][Math.floor(Math.random() * 4)],
    AMOUNT: (Math.random() * 50 + 5).toFixed(1),
    DIRECTION: Math.random() > 0.5 ? 'Hawkish' : 'Dovish',
    SECTOR: SECTORS[Math.floor(Math.random() * SECTORS.length)],
    METRIC: ['Jobs', 'GDP', 'Inflation', 'Manufacturing'][Math.floor(Math.random() * 4)],
    YEAR: new Date().getFullYear(),
    EVENT: ['CEO Resigns', 'Data Breach Reported', 'Regulatory Probe Initiated', 'Supply Chain Issues'][Math.floor(Math.random() * 4)],
    ACTION: ['Raises', 'Maintains', 'Lowers'][Math.floor(Math.random() * 3)],
    TARGET_PRICE: Math.floor(Math.random() * 500 + 50),
    REGION: ['Asia-Pacific', 'Europe', 'Latin America', 'Middle East'][Math.floor(Math.random() * 4)],
  };
  
  let headline = template.headline;
  Object.entries(variables).forEach(([key, value]) => {
    headline = headline.replace(`{${key}}`, value);
  });
  
  const summaries = [
    `Analysts are reacting to the latest developments, with trading volume spiking ${(Math.random() * 200 + 50).toFixed(0)}% above average.`,
    `Market participants are closely monitoring the situation as implications ripple across related sectors.`,
    `The announcement comes amid broader market volatility, with investors seeking clarity on forward guidance.`,
    `Industry experts suggest this could signal a broader trend in the ${variables.SECTOR} space.`,
    `Trading desks report elevated activity in options markets as hedging strategies are adjusted.`,
  ];
  
  const now = new Date();
  const minutesAgo = Math.floor(Math.random() * 120);
  
  return {
    id: `news-${Date.now()}-${Math.random()}`,
    headline,
    summary: summaries[Math.floor(Math.random() * summaries.length)],
    source: sources[Math.floor(Math.random() * sources.length)],
    category: template.category,
    sentiment: template.sentiment,
    symbols: [symbol, Math.random() > 0.7 ? symbols[Math.floor(Math.random() * symbols.length)] : null].filter(Boolean),
    sector: variables.SECTOR,
    timestamp: new Date(now.getTime() - minutesAgo * 60000).toISOString(),
    url: '#',
    isBreaking: Math.random() > 0.9,
    isFeatured: Math.random() > 0.95,
    priceImpact: (Math.random() - 0.5) * 5, // -2.5% to +2.5%
    readTime: Math.floor(Math.random() * 5) + 1,
  };
};

// Sentiment Badge Component
const SentimentBadge = ({ sentiment }) => {
  const config = {
    positive: { icon: TrendingUp, color: 'text-green-400', bg: 'bg-green-500/10', label: 'Bullish' },
    negative: { icon: TrendingDown, color: 'text-red-400', bg: 'bg-red-500/10', label: 'Bearish' },
    neutral: { icon: Minus, color: 'text-slate-400', bg: 'bg-slate-500/10', label: 'Neutral' },
  };
  
  const { icon: Icon, color, bg, label } = config[sentiment] || config.neutral;
  
  return (
    <span className={tw("flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium", bg, color)}>
      <Icon className="w-3 h-3" />
      <span className="hidden sm:inline">{label}</span>
    </span>
  );
};

// Source Badge Component
const SourceBadge = ({ source }) => {
  const sourceConfig = NEWS_SOURCES.find(s => s.id === source);
  
  return (
    <span className="text-xs font-medium text-slate-400">
      {sourceConfig?.name || source}
    </span>
  );
};

// Time Ago Component
const TimeAgo = ({ timestamp }) => {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);
  
  let text;
  if (diff < 60) text = `${diff}s ago`;
  else if (diff < 3600) text = `${Math.floor(diff / 60)}m ago`;
  else if (diff < 86400) text = `${Math.floor(diff / 3600)}h ago`;
  else text = `${Math.floor(diff / 86400)}d ago`;
  
  return (
    <span className="flex items-center gap-1 text-xs text-slate-500">
      <Clock className="w-3 h-3" />
      {text}
    </span>
  );
};

// News Article Card Component
const NewsArticle = ({ article, expanded, onToggle, highlightedKeywords }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [isBookmarked, setIsBookmarked] = useState(false);
  
  const highlightText = (text) => {
    if (!highlightedKeywords.length) return text;
    
    const regex = new RegExp(`(${highlightedKeywords.join('|')})`, 'gi');
    const parts = text.split(regex);
    
    return parts.map((part, i) => 
      highlightedKeywords.some(k => k.toLowerCase() === part.toLowerCase()) ? (
        <mark key={i} className="bg-yellow-500/30 text-yellow-200 px-0.5 rounded">{part}</mark>
      ) : part
    );
  };

  return (
    <div 
      className={tw(
        "border-b border-slate-800/50 transition-colors",
        article.isBreaking ? "bg-red-500/5" : "",
        article.isFeatured ? "bg-blue-500/5" : "",
        isHovered ? "bg-slate-800/30" : ""
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="p-3 cursor-pointer" onClick={onToggle}>
        {/* Header Row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {/* Meta Row */}
            <div className="flex items-center gap-2 mb-1.5">
              {article.isBreaking && (
                <span className="flex items-center gap-1 px-1.5 py-0.5 bg-red-500 text-white text-xs font-semibold rounded">
                  <AlertTriangle className="w-3 h-3" />
                  BREAKING
                </span>
              )}
              <SourceBadge source={article.source} />
              <span className="text-slate-600">•</span>
              <TimeAgo timestamp={article.timestamp} />
              <span className="text-slate-600">•</span>
              <span className="text-xs text-slate-500">{article.readTime} min read</span>
            </div>
            
            {/* Headline */}
            <h3 className={tw(
              "text-sm font-medium leading-snug",
              article.isBreaking ? "text-red-200" : "text-slate-200"
            )}>
              {highlightText(article.headline)}
            </h3>
          </div>
          
          {/* Right Side */}
          <div className="flex flex-col items-end gap-2">
            <SentimentBadge sentiment={article.sentiment} />
            {article.priceImpact !== 0 && (
              <span className={tw(
                "text-xs font-mono",
                article.priceImpact > 0 ? "text-green-400" : "text-red-400"
              )}>
                {article.priceImpact > 0 ? '+' : ''}{article.priceImpact.toFixed(2)}%
              </span>
            )}
          </div>
        </div>
        
        {/* Symbols */}
        {article.symbols.length > 0 && (
          <div className="flex items-center gap-2 mt-2">
            {article.symbols.map(symbol => (
              <span 
                key={symbol}
                className="px-2 py-0.5 bg-slate-800 text-slate-300 text-xs font-mono rounded hover:bg-slate-700 cursor-pointer"
              >
                {symbol}
              </span>
            ))}
            <span className="text-xs text-slate-500">{article.sector}</span>
          </div>
        )}
        
        {/* Expanded Content */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-slate-800/50">
            <p className="text-sm text-slate-400 leading-relaxed">
              {highlightText(article.summary)}
            </p>
            
            {/* Actions */}
            <div className="flex items-center gap-2 mt-3">
              <button 
                onClick={(e) => { e.stopPropagation(); setIsBookmarked(!isBookmarked); }}
                className={tw(
                  "flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors",
                  isBookmarked ? "text-yellow-400 bg-yellow-400/10" : "text-slate-400 hover:bg-slate-800"
                )}
              >
                <Bookmark className={tw("w-3 h-3", isBookmarked && "fill-current")} />
                {isBookmarked ? 'Saved' : 'Save'}
              </button>
              <button className="flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:bg-slate-800 transition-colors">
                <Share2 className="w-3 h-3" />
                Share
              </button>
              <button className="flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:bg-slate-800 transition-colors">
                <Bell className="w-3 h-3" />
                Alert
              </button>
              <a 
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-blue-400 hover:bg-blue-500/10 transition-colors ml-auto"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="w-3 h-3" />
                Read More
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// News Ticker Component
const NewsTicker = ({ articles }) => {
  const tickerRef = useRef(null);
  
  useEffect(() => {
    if (!tickerRef.current) return;
    
    const ticker = tickerRef.current;
    let position = 0;
    
    const animate = () => {
      position -= 1;
      if (position <= -ticker.scrollWidth / 2) {
        position = 0;
      }
      ticker.style.transform = `translateX(${position}px)`;
      requestAnimationFrame(animate);
    };
    
    const animation = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animation);
  }, [articles]);
  
  const breakingNews = articles.filter(a => a.isBreaking || Date.now() - new Date(a.timestamp) < 300000);
  
  if (breakingNews.length === 0) return null;
  
  return (
    <div className="h-8 bg-gradient-to-r from-red-900/50 via-red-800/30 to-red-900/50 border-b border-red-500/20 overflow-hidden">
      <div className="flex items-center h-full">
        <span className="px-3 py-1 bg-red-500 text-white text-xs font-semibold z-10">
          <AlertTriangle className="w-3 h-3 inline mr-1" />
          BREAKING
        </span>
        <div className="flex-1 overflow-hidden relative">
          <div ref={tickerRef} className="flex items-center gap-8 whitespace-nowrap">
            {[...breakingNews, ...breakingNews].map((article, i) => (
              <span key={`${article.id}-${i}`} className="text-sm text-red-200">
                {article.headline}
                <span className="mx-4 text-red-500">•</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// Filter Panel Component
const FilterPanel = ({ filters, onChange, onClose }) => {
  const [localFilters, setLocalFilters] = useState(filters);
  
  const toggleArrayFilter = (key, value) => {
    setLocalFilters(prev => {
      const current = prev[key] || [];
      const updated = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value];
      return { ...prev, [key]: updated };
    });
  };
  
  return (
    <div className="absolute right-0 top-full mt-1 w-72 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-20">
      <div className="flex items-center justify-between p-3 border-b border-slate-800">
        <span className="font-medium text-slate-200">Filters</span>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
          <X className="w-4 h-4" />
        </button>
      </div>
      
      <div className="p-3 max-h-96 overflow-y-auto">
        {/* Sources */}
        <div className="mb-4">
          <span className="text-xs font-medium text-slate-500 uppercase">Sources</span>
          <div className="flex flex-wrap gap-2 mt-2">
            {NEWS_SOURCES.map(source => (
              <button
                key={source.id}
                onClick={() => toggleArrayFilter('sources', source.id)}
                className={tw(
                  "px-2 py-1 text-xs rounded transition-colors",
                  localFilters.sources?.includes(source.id)
                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/50"
                    : "bg-slate-800 text-slate-400 border border-slate-700"
                )}
              >
                {source.name}
              </button>
            ))}
          </div>
        </div>
        
        {/* Sectors */}
        <div className="mb-4">
          <span className="text-xs font-medium text-slate-500 uppercase">Sectors</span>
          <div className="flex flex-wrap gap-2 mt-2">
            {SECTORS.map(sector => (
              <button
                key={sector}
                onClick={() => toggleArrayFilter('sectors', sector)}
                className={tw(
                  "px-2 py-1 text-xs rounded transition-colors",
                  localFilters.sectors?.includes(sector)
                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/50"
                    : "bg-slate-800 text-slate-400 border border-slate-700"
                )}
              >
                {sector}
              </button>
            ))}
          </div>
        </div>
        
        {/* Sentiment */}
        <div className="mb-4">
          <span className="text-xs font-medium text-slate-500 uppercase">Sentiment</span>
          <div className="flex gap-2 mt-2">
            {['positive', 'neutral', 'negative'].map(sentiment => (
              <button
                key={sentiment}
                onClick={() => setLocalFilters(prev => ({ 
                  ...prev, 
                  sentiment: prev.sentiment === sentiment ? null : sentiment 
                }))}
                className={tw(
                  "flex-1 px-2 py-1 text-xs rounded capitalize transition-colors",
                  localFilters.sentiment === sentiment
                    ? sentiment === 'positive' ? "bg-green-500/20 text-green-400 border border-green-500/50"
                    : sentiment === 'negative' ? "bg-red-500/20 text-red-400 border border-red-500/50"
                    : "bg-slate-500/20 text-slate-400 border border-slate-500/50"
                    : "bg-slate-800 text-slate-400 border border-slate-700"
                )}
              >
                {sentiment}
              </button>
            ))}
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex gap-2 pt-3 border-t border-slate-800">
          <button
            onClick={() => { setLocalFilters({}); onChange({}); }}
            className="flex-1 px-3 py-2 text-xs bg-slate-800 text-slate-300 rounded hover:bg-slate-700"
          >
            Reset
          </button>
          <button
            onClick={() => onChange(localFilters)}
            className="flex-1 px-3 py-2 text-xs bg-blue-600 text-white rounded hover:bg-blue-500"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
};

const NewsFeed = () => {
  const { 
    articles, 
    filters, 
    highlightedKeywords,
    addArticle, 
    setFilters,
    addHighlightedKeyword,
    removeHighlightedKeyword,
  } = useNewsStore();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [expandedArticle, setExpandedArticle] = useState(null);
  const [isPaused, setIsPaused] = useState(false);
  const [viewMode, setViewMode] = useState('feed'); // 'feed', 'compact'

  // Simulate incoming news
  useEffect(() => {
    if (isPaused) return;
    
    // Initial articles
    if (articles.length === 0) {
      for (let i = 0; i < 20; i++) {
        addArticle(generateNewsArticle());
      }
    }
    
    const interval = setInterval(() => {
      if (Math.random() > 0.7) {
        addArticle(generateNewsArticle());
      }
    }, 3000);
    
    return () => clearInterval(interval);
  }, [isPaused, articles.length]);

  // Filter articles
  const filteredArticles = useMemo(() => {
    let result = [...articles];
    
    // Apply filters
    if (filters.sources?.length > 0) {
      result = result.filter(a => filters.sources.includes(a.source));
    }
    if (filters.sectors?.length > 0) {
      result = result.filter(a => filters.sectors.includes(a.sector));
    }
    if (filters.sentiment) {
      result = result.filter(a => a.sentiment === filters.sentiment);
    }
    
    // Apply search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(a => 
        a.headline.toLowerCase().includes(query) ||
        a.summary.toLowerCase().includes(query) ||
        a.symbols.some(s => s.toLowerCase().includes(query))
      );
    }
    
    return result;
  }, [articles, filters, searchQuery]);

  // Stats
  const stats = useMemo(() => {
    const total = filteredArticles.length;
    const bullish = filteredArticles.filter(a => a.sentiment === 'positive').length;
    const bearish = filteredArticles.filter(a => a.sentiment === 'negative').length;
    const neutral = filteredArticles.filter(a => a.sentiment === 'neutral').length;
    const breaking = filteredArticles.filter(a => a.isBreaking).length;
    
    return { total, bullish, bearish, neutral, breaking };
  }, [filteredArticles]);

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-slate-100">News Feed</h3>
          <div className="hidden sm:flex items-center gap-2 text-xs">
            <span className="px-1.5 py-0.5 bg-green-500/10 text-green-400 rounded">
              {stats.bullish} Bull
            </span>
            <span className="px-1.5 py-0.5 bg-red-500/10 text-red-400 rounded">
              {stats.bearish} Bear
            </span>
            <span className="px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded">
              {stats.neutral} Neutral
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-1">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search news..."
              className="w-32 sm:w-40 pl-7 pr-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Pause/Play */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={tw(
              "p-1.5 rounded transition-colors",
              isPaused ? "text-yellow-400 bg-yellow-400/10" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            )}
          >
            {isPaused ? <BarChart3 className="w-4 h-4" /> : <RefreshCw className="w-4 h-4" />}
          </button>

          {/* Filters */}
          <div className="relative">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={tw(
                "p-1.5 rounded transition-colors",
                showFilters || Object.keys(filters).some(k => filters[k]?.length > 0)
                  ? "text-blue-400 bg-blue-500/10"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              )}
            >
              <Filter className="w-4 h-4" />
            </button>
            
            {showFilters && (
              <FilterPanel
                filters={filters}
                onChange={(newFilters) => { setFilters(newFilters); setShowFilters(false); }}
                onClose={() => setShowFilters(false)}
              />
            )}
          </div>
        </div>
      </div>

      {/* Breaking News Ticker */}
      <NewsTicker articles={articles} />

      {/* Stats Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-800 bg-slate-950/50 text-xs">
        <span className="text-slate-500">{stats.total} articles</span>
        <div className="flex items-center gap-3">
          <span className="text-slate-500">
            Breaking: <span className="text-red-400">{stats.breaking}</span>
          </span>
          {highlightedKeywords.length > 0 && (
            <div className="flex items-center gap-1">
              <span className="text-slate-500">Highlighting:</span>
              {highlightedKeywords.map(kw => (
                <span key={kw} className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">
                  {kw}
                  <X 
                    className="w-3 h-3 inline ml-1 cursor-pointer hover:text-yellow-200" 
                    onClick={() => removeHighlightedKeyword(kw)}
                  />
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Articles List */}
      <div className="flex-1 overflow-y-auto">
        {filteredArticles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500">
            <Newspaper className="w-12 h-12 mb-4 opacity-50" />
            <p>No news articles found</p>
            <p className="text-xs mt-1">Try adjusting your filters</p>
          </div>
        ) : (
          filteredArticles.map(article => (
            <NewsArticle
              key={article.id}
              article={article}
              expanded={expandedArticle === article.id}
              onToggle={() => setExpandedArticle(
                expandedArticle === article.id ? null : article.id
              )}
              highlightedKeywords={highlightedKeywords}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default NewsFeed;
