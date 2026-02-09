export const API = {
  FRANKFURTER: {
    latest: 'https://api.frankfurter.dev/v1/latest',
    historical: (date: string): string => `https://api.frankfurter.dev/v1/${date}`,
    timeseries: (from: string, to: string): string => `https://api.frankfurter.dev/v1/${from}..${to}`,
  },
  COINGECKO: {
    prices: 'https://api.coingecko.com/api/v3/simple/price',
    markets: 'https://api.coingecko.com/api/v3/coins/markets',
    coin: (id: string): string => `https://api.coingecko.com/api/v3/coins/${id}`,
  },
  FMP: {
    quote: (sym: string, key: string): string => `https://financialmodelingprep.com/api/v3/quote/${sym}?apikey=${key}`,
    profile: (sym: string, key: string): string => `https://financialmodelingprep.com/api/v3/profile/${sym}?apikey=${key}`,
    historical: (sym: string, key: string): string => `https://financialmodelingprep.com/api/v3/historical-price-full/${sym}?apikey=${key}`,
    marketMost: (type: string, key: string): string => `https://financialmodelingprep.com/api/v3/stock_market/${type}?apikey=${key}`,
  },
  FRED: {
    series: (id: string, key: string): string => `/api/fred/fred/series/observations?series_id=${id}&api_key=${key}&file_type=json`,
  },
  FINNHUB: {
    quote: (sym: string, key: string): string => `https://finnhub.io/api/v1/quote?symbol=${sym}&token=${key}`,
    news: (cat: string, key: string): string => `https://finnhub.io/api/v1/news?category=${cat}&token=${key}`,
    candles: (sym: string, res: string, from: number, to: number, key: string): string => `https://finnhub.io/api/v1/stock/candle?symbol=${sym}&resolution=${res}&from=${from}&to=${to}&token=${key}`,
    earnings: (from: string, to: string, key: string): string => `https://finnhub.io/api/v1/calendar/earnings?from=${from}&to=${to}&token=${key}`,
  },
  WORLD_BANK: {
    indicator: (country: string, ind: string): string => `https://api.worldbank.org/v2/country/${country}/indicator/${ind}?format=json&per_page=50`,
  },
  GNEWS: {
    search: (q: string, key: string): string => `https://gnews.io/api/v4/search?q=${encodeURIComponent(q)}&token=${key}&lang=en&max=10`,
  },
  YAHOO: {
    quote: (symbols: string): string => `/api/yahoo/v7/finance/quote?symbols=${symbols}`,
  },
  ALPHA_VANTAGE: {
    quote: (sym: string, key: string): string => `https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${sym}&apikey=${key}`,
  },
  RSS2JSON: {
    convert: (rssUrl: string): string => `/api/rss/v1/api.json?rss_url=${encodeURIComponent(rssUrl)}`,
  },
  NEWSDATA: {
    latest: (key: string, q: string): string => `https://newsdata.io/api/1/latest?apikey=${key}&q=${encodeURIComponent(q)}&language=en&category=business`,
    headlines: (key: string): string => `https://newsdata.io/api/1/latest?apikey=${key}&language=en&category=business`,
  },
  NEWSAPI_ORG: {
    headlines: (key: string): string => `https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=20&apiKey=${key}`,
    search: (key: string, q: string): string => `https://newsapi.org/v2/everything?q=${encodeURIComponent(q)}&language=en&sortBy=publishedAt&pageSize=20&apiKey=${key}`,
  },
  WORLD_NEWS_API: {
    search: (key: string, q: string): string => `https://api.worldnewsapi.com/search-news?text=${encodeURIComponent(q)}&language=en&number=20&api-key=${key}`,
    headlines: (key: string): string => `https://api.worldnewsapi.com/top-news?source-country=us&language=en&api-key=${key}`,
  },
  BINANCE_WS: 'wss://stream.binance.com:9443/ws',
  FINNHUB_WS: (key: string): string => `wss://ws.finnhub.io?token=${key}`,
};
