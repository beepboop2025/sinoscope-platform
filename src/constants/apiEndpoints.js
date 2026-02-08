export const API = {
  FRANKFURTER: {
    latest: 'https://api.frankfurter.dev/v1/latest',
    historical: (date) => `https://api.frankfurter.dev/v1/${date}`,
    timeseries: (from, to) => `https://api.frankfurter.dev/v1/${from}..${to}`,
  },
  COINGECKO: {
    prices: 'https://api.coingecko.com/api/v3/simple/price',
    markets: 'https://api.coingecko.com/api/v3/coins/markets',
    coin: (id) => `https://api.coingecko.com/api/v3/coins/${id}`,
  },
  FMP: {
    quote: (sym, key) => `https://financialmodelingprep.com/api/v3/quote/${sym}?apikey=${key}`,
    profile: (sym, key) => `https://financialmodelingprep.com/api/v3/profile/${sym}?apikey=${key}`,
    historical: (sym, key) => `https://financialmodelingprep.com/api/v3/historical-price-full/${sym}?apikey=${key}`,
    marketMost: (type, key) => `https://financialmodelingprep.com/api/v3/stock_market/${type}?apikey=${key}`,
  },
  FRED: {
    series: (id, key) => `/api/fred/fred/series/observations?series_id=${id}&api_key=${key}&file_type=json`,
  },
  FINNHUB: {
    quote: (sym, key) => `https://finnhub.io/api/v1/quote?symbol=${sym}&token=${key}`,
    news: (cat, key) => `https://finnhub.io/api/v1/news?category=${cat}&token=${key}`,
    candles: (sym, res, from, to, key) => `https://finnhub.io/api/v1/stock/candle?symbol=${sym}&resolution=${res}&from=${from}&to=${to}&token=${key}`,
  },
  WORLD_BANK: {
    indicator: (country, ind) => `https://api.worldbank.org/v2/country/${country}/indicator/${ind}?format=json&per_page=50`,
    commodity: 'https://api.worldbank.org/v2/country/WLD/indicator/',
  },
  GNEWS: {
    search: (q, key) => `https://gnews.io/api/v4/search?q=${encodeURIComponent(q)}&token=${key}&lang=en&max=10`,
  },
  YAHOO: {
    quote: (symbols) => `/api/yahoo/v7/finance/quote?symbols=${symbols}`,
  },
  ALPHA_VANTAGE: {
    quote: (sym, key) => `https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${sym}&apikey=${key}`,
  },
  RSS2JSON: {
    convert: (rssUrl) => `/api/rss/v1/api.json?rss_url=${encodeURIComponent(rssUrl)}`,
  },
  BINANCE_WS: 'wss://stream.binance.com:9443/ws',
  FINNHUB_WS: (key) => `wss://ws.finnhub.io?token=${key}`,
};
