interface CommandEntry {
  readonly id: string;
  readonly label: string;
  readonly desc: string;
  readonly shortcut?: string;
  readonly action: string;
  readonly target?: string;
}

export const COMMANDS: readonly CommandEntry[] = [
  { id: 'overview', label: 'Overview', desc: 'Default workspace', shortcut: '1', action: 'workspace', target: 'overview' },
  { id: 'china', label: 'China Focus', desc: 'China markets workspace', shortcut: '2', action: 'workspace', target: 'china' },
  { id: 'correlation', label: 'Cross-Market Analysis', desc: 'Correlation workspace', shortcut: '3', action: 'workspace', target: 'correlation' },
  { id: 'forex_ws', label: 'Forex', desc: 'Forex workspace', shortcut: '4', action: 'workspace', target: 'forex' },
  { id: 'fi', label: 'Fixed Income', desc: 'Bonds workspace', shortcut: '5', action: 'workspace', target: 'fixedIncome' },
  { id: 'research', label: 'Research', desc: 'GitHub & HuggingFace data', shortcut: '6', action: 'workspace', target: 'research' },
  { id: 'sentiment_ws', label: 'Sentiment', desc: 'Market sentiment workspace', shortcut: '7', action: 'workspace', target: 'sentiment' },
  { id: 'defi_ws', label: 'DeFi & Crypto', desc: 'DeFi protocols & crypto global', shortcut: '8', action: 'workspace', target: 'defiCrypto' },
  { id: 'ml_ws', label: 'ML Analytics', desc: 'Neural network predictions & signals', shortcut: '9', action: 'workspace', target: 'mlAnalytics' },
  { id: 'add_forex', label: 'Add Forex Panel', desc: 'Add forex rates panel', action: 'addPanel', target: 'forex' },
  { id: 'add_stocks', label: 'Add Stocks Panel', desc: 'Add stock watchlist', action: 'addPanel', target: 'stocks' },
  { id: 'add_crypto', label: 'Add Crypto Panel', desc: 'Add crypto panel', action: 'addPanel', target: 'crypto' },
  { id: 'add_bonds', label: 'Add Bonds Panel', desc: 'Add bond yields', action: 'addPanel', target: 'bonds' },
  { id: 'add_news', label: 'Add News Panel', desc: 'Add news feed', action: 'addPanel', target: 'news' },
  { id: 'add_correlation', label: 'Add Correlation', desc: 'Add correlation matrix', action: 'addPanel', target: 'correlation' },
  { id: 'add_china', label: 'Add China Markets', desc: 'Add China panel', action: 'addPanel', target: 'chinaMarkets' },
  { id: 'add_sql', label: 'Add SQL Query', desc: 'Add SQL query panel', action: 'addPanel', target: 'sqlQuery' },
  { id: 'add_github', label: 'Add GitHub Panel', desc: 'Add trending finance repos', action: 'addPanel', target: 'githubTrending' },
  { id: 'add_hf', label: 'Add HuggingFace Panel', desc: 'Add ML finance models', action: 'addPanel', target: 'huggingFace' },
  { id: 'add_sentiment', label: 'Add Sentiment Panel', desc: 'Add Fear & Greed Index', action: 'addPanel', target: 'sentiment' },
  { id: 'add_sectors', label: 'Add Sectors Panel', desc: 'Add sector heatmap', action: 'addPanel', target: 'sectors' },
  { id: 'add_watchlist', label: 'Add Watchlist Panel', desc: 'Add custom watchlist', action: 'addPanel', target: 'watchlist' },
  { id: 'add_defi', label: 'Add DeFi Panel', desc: 'Add DeFi TVL tracker', action: 'addPanel', target: 'defi' },
  { id: 'add_cglobal', label: 'Add Crypto Global', desc: 'Add crypto market overview', action: 'addPanel', target: 'cryptoGlobal' },
  { id: 'add_reddit', label: 'Add Reddit Panel', desc: 'Add Reddit finance sentiment', action: 'addPanel', target: 'redditSentiment' },
  { id: 'add_sec', label: 'Add SEC Filings', desc: 'Add SEC EDGAR filings', action: 'addPanel', target: 'secFilings' },
  { id: 'add_research', label: 'Add Research Papers', desc: 'Add arXiv finance papers', action: 'addPanel', target: 'researchPapers' },
  { id: 'add_ml', label: 'Add ML Dashboard', desc: 'Add neural network dashboard', action: 'addPanel', target: 'mlDashboard' },
  { id: 'add_signals', label: 'Add Trading Signals', desc: 'Add ML trading signals', action: 'addPanel', target: 'signals' },
  { id: 'add_candlestick', label: 'Add Candlestick Chart', desc: 'Add TradingView candlestick chart', action: 'addPanel', target: 'candlestick' },
  { id: 'add_portfolio', label: 'Add Portfolio', desc: 'Add portfolio tracker with P&L', action: 'addPanel', target: 'portfolio' },
  { id: 'add_earnings', label: 'Add Earnings Calendar', desc: 'Add upcoming earnings calendar', action: 'addPanel', target: 'earningsCalendar' },
  { id: 'export', label: 'Export Data', desc: 'Export current data as JSON', action: 'export' },
] as const;
