/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
  readonly VITE_FINNHUB_API_KEY?: string
  readonly VITE_FRED_API_KEY?: string
  readonly VITE_FMP_API_KEY?: string
  readonly VITE_ALPHA_VANTAGE_API_KEY?: string
  readonly VITE_GNEWS_API_KEY?: string
  readonly VITE_NEWSDATA_API_KEY?: string
  readonly VITE_NEWSAPI_API_KEY?: string
  readonly VITE_WORLD_NEWS_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
