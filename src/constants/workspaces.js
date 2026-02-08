export const DEFAULT_WORKSPACES = {
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
    ],
    panels: ['forex', 'stocks', 'crypto', 'bonds', 'commodities', 'news'],
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
    ],
    panels: ['correlation', 'network', 'timeline'],
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
};

export const PANEL_REGISTRY = {
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
};
