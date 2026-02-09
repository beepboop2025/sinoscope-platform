export const FOREX_PAIRS = [
  { symbol: 'EUR/USD', base: 'EUR', quote: 'USD', name: 'Euro/Dollar' },
  { symbol: 'GBP/USD', base: 'GBP', quote: 'USD', name: 'Pound/Dollar' },
  { symbol: 'USD/JPY', base: 'USD', quote: 'JPY', name: 'Dollar/Yen' },
  { symbol: 'USD/CHF', base: 'USD', quote: 'CHF', name: 'Dollar/Swiss' },
  { symbol: 'AUD/USD', base: 'AUD', quote: 'USD', name: 'Aussie/Dollar' },
  { symbol: 'USD/CAD', base: 'USD', quote: 'CAD', name: 'Dollar/Loonie' },
  { symbol: 'NZD/USD', base: 'NZD', quote: 'USD', name: 'Kiwi/Dollar' },
  { symbol: 'USD/CNY', base: 'USD', quote: 'CNY', name: 'Dollar/Yuan' },
  { symbol: 'USD/CNH', base: 'USD', quote: 'CNH', name: 'Dollar/Yuan Offshore' },
  { symbol: 'USD/HKD', base: 'USD', quote: 'HKD', name: 'Dollar/HK Dollar' },
  { symbol: 'USD/INR', base: 'USD', quote: 'INR', name: 'Dollar/Rupee' },
  { symbol: 'EUR/GBP', base: 'EUR', quote: 'GBP', name: 'Euro/Pound' },
  { symbol: 'EUR/JPY', base: 'EUR', quote: 'JPY', name: 'Euro/Yen' },
];

export const STOCK_SYMBOLS = [
  { symbol: 'AAPL', name: 'Apple', exchange: 'NASDAQ' },
  { symbol: 'MSFT', name: 'Microsoft', exchange: 'NASDAQ' },
  { symbol: 'GOOGL', name: 'Alphabet', exchange: 'NASDAQ' },
  { symbol: 'AMZN', name: 'Amazon', exchange: 'NASDAQ' },
  { symbol: 'NVDA', name: 'NVIDIA', exchange: 'NASDAQ' },
  { symbol: 'TSLA', name: 'Tesla', exchange: 'NASDAQ' },
  { symbol: 'META', name: 'Meta', exchange: 'NASDAQ' },
  { symbol: 'JPM', name: 'JPMorgan', exchange: 'NYSE' },
  { symbol: 'V', name: 'Visa', exchange: 'NYSE' },
  { symbol: 'JNJ', name: 'Johnson & Johnson', exchange: 'NYSE' },
];

export const CRYPTO_SYMBOLS = [
  { symbol: 'BTC', name: 'Bitcoin', pair: 'btcusdt' },
  { symbol: 'ETH', name: 'Ethereum', pair: 'ethusdt' },
  { symbol: 'BNB', name: 'Binance Coin', pair: 'bnbusdt' },
  { symbol: 'SOL', name: 'Solana', pair: 'solusdt' },
  { symbol: 'XRP', name: 'Ripple', pair: 'xrpusdt' },
  { symbol: 'ADA', name: 'Cardano', pair: 'adausdt' },
  { symbol: 'DOGE', name: 'Dogecoin', pair: 'dogeusdt' },
  { symbol: 'DOT', name: 'Polkadot', pair: 'dotusdt' },
];

export const COMMODITY_SYMBOLS = [
  { symbol: 'GOLD', name: 'Gold', unit: '$/oz' },
  { symbol: 'SILVER', name: 'Silver', unit: '$/oz' },
  { symbol: 'OIL_WTI', name: 'Crude Oil WTI', unit: '$/bbl' },
  { symbol: 'OIL_BRENT', name: 'Crude Oil Brent', unit: '$/bbl' },
  { symbol: 'NATGAS', name: 'Natural Gas', unit: '$/mmBtu' },
  { symbol: 'COPPER', name: 'Copper', unit: '$/lb' },
  { symbol: 'WHEAT', name: 'Wheat', unit: '$/bu' },
  { symbol: 'CORN', name: 'Corn', unit: '$/bu' },
];

export const INDEX_SYMBOLS = [
  { symbol: 'SPX', name: 'S&P 500', exchange: 'NYSE' },
  { symbol: 'DJI', name: 'Dow Jones', exchange: 'NYSE' },
  { symbol: 'IXIC', name: 'NASDAQ Composite', exchange: 'NASDAQ' },
  { symbol: 'FTSE', name: 'FTSE 100', exchange: 'LSE' },
  { symbol: 'DAX', name: 'DAX 40', exchange: 'XETRA' },
  { symbol: 'N225', name: 'Nikkei 225', exchange: 'TSE' },
  { symbol: 'SSEC', name: 'SSE Composite', exchange: 'SSE' },
  { symbol: 'HSI', name: 'Hang Seng', exchange: 'HKEX' },
];

export const BOND_MATURITIES = ['1M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y'];
