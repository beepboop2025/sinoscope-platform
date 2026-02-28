/**
 * Feature flags driven by environment variables.
 * Shows which features are available based on configured API keys.
 */

interface FeatureFlags {
  /** Real-time stock data via Alpha Vantage / FMP / Finnhub */
  hasStockData: boolean;
  /** FRED API for bonds, economic data, commodities */
  hasFredData: boolean;
  /** Live news from any news provider */
  hasNewsKeys: boolean;
  /** Real-time WebSocket via Finnhub */
  hasFinnhubWS: boolean;
  /** Clerk authentication */
  hasAuth: boolean;
  /** Overall: true if any API key is configured */
  isLiveMode: boolean;
}

export function getFeatureFlags(): FeatureFlags {
  const env = import.meta.env;

  const hasStockData = !!(env.VITE_ALPHA_VANTAGE_API_KEY || env.VITE_FMP_API_KEY || env.VITE_FINNHUB_API_KEY);
  const hasFredData = !!env.VITE_FRED_API_KEY;
  const hasNewsKeys = !!(
    env.VITE_FINNHUB_API_KEY ||
    env.VITE_NEWSDATA_API_KEY ||
    env.VITE_NEWSAPI_API_KEY ||
    env.VITE_WORLD_NEWS_API_KEY ||
    env.VITE_GNEWS_API_KEY
  );
  const hasFinnhubWS = !!env.VITE_FINNHUB_API_KEY;
  const hasAuth = !!env.VITE_CLERK_PUBLISHABLE_KEY;

  return {
    hasStockData,
    hasFredData,
    hasNewsKeys,
    hasFinnhubWS,
    hasAuth,
    isLiveMode: hasStockData || hasFredData || hasNewsKeys,
  };
}

/** Check if running in demo mode (no API keys configured) */
export function isDemoMode(): boolean {
  return !getFeatureFlags().isLiveMode;
}
