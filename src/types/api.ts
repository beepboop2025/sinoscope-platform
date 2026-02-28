export interface AlphaVantageGlobalQuote {
  'Global Quote': {
    '01. symbol': string;
    '02. open': string;
    '03. high': string;
    '04. low': string;
    '05. price': string;
    '06. volume': string;
    '07. latest trading day': string;
    '08. previous close': string;
    '09. change': string;
    '10. change percent': string;
  };
}

export interface CoinGeckoMarketItem {
  id: string;
  symbol: string;
  name: string;
  image: string;
  current_price: number;
  market_cap: number;
  market_cap_rank: number;
  total_volume: number;
  high_24h: number;
  low_24h: number;
  price_change_24h: number;
  price_change_percentage_24h: number;
  price_change_percentage_1h_in_currency?: number;
  price_change_percentage_7d_in_currency?: number;
  sparkline_in_7d?: { price: number[] };
  circulating_supply: number;
  total_supply: number | null;
  ath: number;
  ath_change_percentage: number;
}

export interface FinnhubQuote {
  c: number;  // current
  d: number;  // change
  dp: number; // percent change
  h: number;  // high
  l: number;  // low
  o: number;  // open
  pc: number; // previous close
  t: number;  // timestamp
}

export interface FinnhubCandleResponse {
  c: number[];  // close
  h: number[];  // high
  l: number[];  // low
  o: number[];  // open
  s: string;    // status
  t: number[];  // timestamps
  v: number[];  // volumes
}

export interface BinanceTickerMessage {
  e: string;    // event type
  E: number;    // event time
  s: string;    // symbol
  p: string;    // price change
  P: string;    // price change percent
  w: string;    // weighted avg price
  c: string;    // last price
  Q: string;    // last quantity
  o: string;    // open price
  h: string;    // high price
  l: string;    // low price
  v: string;    // total traded volume
  q: string;    // total traded quote volume
}

export type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WSCallbacks {
  onMessage: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

export interface WSConnection {
  ws: WebSocket;
  callbacks: WSCallbacks;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  intentionalClose: boolean;
}

export interface ApiFetchOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

export interface ApiClient {
  getMe: () => Promise<unknown>;
  syncUser: (data: unknown) => Promise<unknown>;
  updatePreferences: (prefs: unknown) => Promise<unknown>;
  getPortfolios: () => Promise<unknown>;
  createPortfolio: (data: unknown) => Promise<unknown>;
  updatePortfolio: (id: string, data: unknown) => Promise<unknown>;
  deletePortfolio: (id: string) => Promise<unknown>;
  addHolding: (portfolioId: string, data: unknown) => Promise<unknown>;
  removeHolding: (portfolioId: string, holdingId: string) => Promise<unknown>;
  getWatchlists: () => Promise<unknown>;
  createWatchlist: (data: unknown) => Promise<unknown>;
  deleteWatchlist: (id: string) => Promise<unknown>;
  addWatchlistItem: (watchlistId: string, data: unknown) => Promise<unknown>;
  removeWatchlistItem: (watchlistId: string, itemId: string) => Promise<unknown>;
  getAlerts: () => Promise<unknown>;
  createAlert: (data: unknown) => Promise<unknown>;
  updateAlert: (id: string, data: unknown) => Promise<unknown>;
  deleteAlert: (id: string) => Promise<unknown>;
  getApiKeys: () => Promise<unknown>;
  saveApiKey: (data: unknown) => Promise<unknown>;
  deleteApiKey: (id: string) => Promise<unknown>;
  getData: (category: string) => Promise<unknown>;

  // History
  getHistoryCandles: (symbol: string, params?: { interval?: string; start?: string; end?: string; limit?: number }) => Promise<unknown>;
  getHistoryTicks: (symbol: string, params?: { start?: string; end?: string; category?: string; limit?: number }) => Promise<unknown>;
  getHistorySymbols: (category?: string) => Promise<unknown>;

  // Analytics
  getCorrelations: (params?: { days?: number; interval?: string; symbols?: string }) => Promise<unknown>;
  getPortfolioAnalytics: (portfolioId: string) => Promise<unknown>;

  // Data Quality
  getDataQuality: () => Promise<unknown>;
}
