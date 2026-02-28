import type { LayoutItem } from '../types';

interface WorkspaceConfig {
  readonly id: string;
  readonly name: string;
  readonly layout: readonly LayoutItem[];
  readonly panels: readonly string[];
}

interface PanelRegistryEntry {
  readonly title: string;
  readonly icon: string;
}

export const DEFAULT_WORKSPACES: Record<string, WorkspaceConfig> = {
  overview: {
    id: 'overview',
    name: 'Overview',
    layout: [
      { i: 'forex', x: 0, y: 0, w: 4, h: 4 },
      { i: 'stocks', x: 4, y: 0, w: 4, h: 4 },
      { i: 'crypto', x: 8, y: 0, w: 4, h: 4 },
      { i: 'bonds', x: 0, y: 4, w: 4, h: 4 },
      { i: 'commodities', x: 4, y: 4, w: 4, h: 4 },
      { i: 'news', x: 8, y: 4, w: 4, h: 4 },
      { i: 'candlestick', x: 0, y: 8, w: 8, h: 5 },
      { i: 'portfolio', x: 8, y: 8, w: 4, h: 5 },
    ],
    panels: ['forex', 'stocks', 'crypto', 'bonds', 'commodities', 'news', 'candlestick', 'portfolio'],
  },
  china: {
    id: 'china',
    name: 'China Focus',
    layout: [
      { i: 'chinaMarkets', x: 0, y: 0, w: 6, h: 4 },
      { i: 'cnyTracker', x: 6, y: 0, w: 6, h: 4 },
      { i: 'pbocWatch', x: 0, y: 4, w: 4, h: 4 },
      { i: 'tradeFlow', x: 4, y: 4, w: 4, h: 4 },
      { i: 'chinaCalendar', x: 8, y: 4, w: 4, h: 4 },
    ],
    panels: ['chinaMarkets', 'cnyTracker', 'pbocWatch', 'tradeFlow', 'chinaCalendar'],
  },
  correlation: {
    id: 'correlation',
    name: 'Cross-Market',
    layout: [
      { i: 'correlation', x: 0, y: 0, w: 6, h: 6 },
      { i: 'network', x: 6, y: 0, w: 6, h: 6 },
      { i: 'timeline', x: 0, y: 6, w: 12, h: 3 },
      { i: 'sqlQuery', x: 0, y: 9, w: 12, h: 5 },
    ],
    panels: ['correlation', 'network', 'timeline', 'sqlQuery'],
  },
  forex: {
    id: 'forex',
    name: 'Forex',
    layout: [
      { i: 'forex', x: 0, y: 0, w: 6, h: 5 },
      { i: 'chart', x: 6, y: 0, w: 6, h: 5 },
      { i: 'economic', x: 0, y: 5, w: 12, h: 4 },
    ],
    panels: ['forex', 'chart', 'economic'],
  },
  fixedIncome: {
    id: 'fixedIncome',
    name: 'Fixed Income',
    layout: [
      { i: 'bonds', x: 0, y: 0, w: 8, h: 5 },
      { i: 'economic', x: 8, y: 0, w: 4, h: 5 },
      { i: 'news', x: 0, y: 5, w: 12, h: 4 },
    ],
    panels: ['bonds', 'economic', 'news'],
  },
  research: {
    id: 'research',
    name: 'Research',
    layout: [
      { i: 'githubTrending', x: 0, y: 0, w: 4, h: 6 },
      { i: 'huggingFace', x: 4, y: 0, w: 4, h: 6 },
      { i: 'researchPapers', x: 8, y: 0, w: 4, h: 6 },
      { i: 'secFilings', x: 0, y: 6, w: 4, h: 5 },
      { i: 'earningsCalendar', x: 4, y: 6, w: 4, h: 5 },
      { i: 'sqlQuery', x: 8, y: 6, w: 4, h: 5 },
    ],
    panels: ['githubTrending', 'huggingFace', 'researchPapers', 'secFilings', 'earningsCalendar', 'sqlQuery'],
  },
  sentiment: {
    id: 'sentiment',
    name: 'Sentiment',
    layout: [
      { i: 'sentiment', x: 0, y: 0, w: 4, h: 5 },
      { i: 'sectors', x: 4, y: 0, w: 4, h: 5 },
      { i: 'watchlist', x: 8, y: 0, w: 4, h: 5 },
      { i: 'redditSentiment', x: 0, y: 5, w: 6, h: 5 },
      { i: 'news', x: 6, y: 5, w: 6, h: 5 },
    ],
    panels: ['sentiment', 'sectors', 'watchlist', 'redditSentiment', 'news'],
  },
  defiCrypto: {
    id: 'defiCrypto',
    name: 'DeFi & Crypto',
    layout: [
      { i: 'defi', x: 0, y: 0, w: 6, h: 6 },
      { i: 'cryptoGlobal', x: 6, y: 0, w: 6, h: 6 },
      { i: 'crypto', x: 0, y: 6, w: 6, h: 4 },
      { i: 'redditSentiment', x: 6, y: 6, w: 6, h: 4 },
    ],
    panels: ['defi', 'cryptoGlobal', 'crypto', 'redditSentiment'],
  },
  mlAnalytics: {
    id: 'mlAnalytics',
    name: 'ML Analytics',
    layout: [
      { i: 'mlDashboard', x: 0, y: 0, w: 5, h: 6 },
      { i: 'signals', x: 5, y: 0, w: 7, h: 6 },
      { i: 'stocks', x: 0, y: 6, w: 4, h: 4 },
      { i: 'crypto', x: 4, y: 6, w: 4, h: 4 },
      { i: 'sentiment', x: 8, y: 6, w: 4, h: 4 },
    ],
    panels: ['mlDashboard', 'signals', 'stocks', 'crypto', 'sentiment'],
  },
};

export const PANEL_REGISTRY: Record<string, PanelRegistryEntry> = {
  forex: { title: 'Forex Rates', icon: 'DollarSign' },
  stocks: { title: 'Stock Watchlist', icon: 'TrendingUp' },
  crypto: { title: 'Crypto Markets', icon: 'Bitcoin' },
  bonds: { title: 'Bond Yields', icon: 'Landmark' },
  commodities: { title: 'Commodities', icon: 'Gem' },
  news: { title: 'News Feed', icon: 'Newspaper' },
  economic: { title: 'Economic Data', icon: 'BarChart3' },
  chart: { title: 'Price Chart', icon: 'LineChart' },
  correlation: { title: 'Correlation Matrix', icon: 'Grid3X3' },
  network: { title: 'Network Graph', icon: 'Share2' },
  timeline: { title: 'Event Timeline', icon: 'Calendar' },
  chinaMarkets: { title: 'China Markets', icon: 'Globe' },
  cnyTracker: { title: 'CNY/CNH Tracker', icon: 'ArrowLeftRight' },
  pbocWatch: { title: 'PBOC Watch', icon: 'Building2' },
  tradeFlow: { title: 'Trade Flow', icon: 'Ship' },
  beltRoad: { title: 'Belt & Road', icon: 'Map' },
  chinaCalendar: { title: 'China Calendar', icon: 'CalendarDays' },
  company: { title: 'Company Profile', icon: 'Building' },
  alerts: { title: 'Alerts', icon: 'Bell' },
  sqlQuery: { title: 'SQL Query', icon: 'Database' },
  githubTrending: { title: 'GitHub Finance', icon: 'Github' },
  huggingFace: { title: 'HuggingFace Models', icon: 'Brain' },
  sentiment: { title: 'Fear & Greed', icon: 'Gauge' },
  sectors: { title: 'Sector Performance', icon: 'LayoutGrid' },
  watchlist: { title: 'Watchlist', icon: 'Eye' },
  defi: { title: 'DeFi TVL', icon: 'Layers' },
  cryptoGlobal: { title: 'Crypto Global', icon: 'Globe2' },
  redditSentiment: { title: 'Reddit Finance', icon: 'MessageCircle' },
  secFilings: { title: 'SEC Filings', icon: 'FileText' },
  researchPapers: { title: 'Research Papers', icon: 'BookOpen' },
  mlDashboard: { title: 'ML Dashboard', icon: 'Brain' },
  signals: { title: 'Trading Signals', icon: 'Radio' },
  candlestick: { title: 'Candlestick Chart', icon: 'CandlestickChart' },
  portfolio: { title: 'Portfolio', icon: 'Briefcase' },
  earningsCalendar: { title: 'Earnings Calendar', icon: 'CalendarCheck' },
  fundamentals: { title: 'Fundamentals', icon: 'FileBarChart' },
  newsFeed: { title: 'News Feed', icon: 'Rss' },
  econCalendar: { title: 'Economic Calendar', icon: 'CalendarClock' },
  screener: { title: 'Screener', icon: 'Filter' },
  heatMap: { title: 'Market Heat Map', icon: 'LayoutGrid' },
  orderBook: { title: 'Order Book', icon: 'BookOpen' },
  indianMarket: { title: 'Indian Market', icon: 'IndianRupee' },
  systemHealth: { title: 'System Health', icon: 'Activity' },
  settings: { title: 'Settings', icon: 'Settings' },
};
