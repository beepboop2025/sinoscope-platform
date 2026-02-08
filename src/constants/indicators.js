export const TECHNICAL_INDICATORS = {
  SMA: { name: 'Simple Moving Average', periods: [20, 50, 200], color: 'var(--blue)' },
  EMA: { name: 'Exponential Moving Average', periods: [12, 26], color: 'var(--purple)' },
  RSI: { name: 'Relative Strength Index', period: 14, overbought: 70, oversold: 30, color: 'var(--amber)' },
  MACD: { name: 'MACD', fast: 12, slow: 26, signal: 9, color: 'var(--cyan)' },
  BOLLINGER: { name: 'Bollinger Bands', period: 20, multiplier: 2, color: 'var(--teal)' },
};

export const ECONOMIC_INDICATORS = {
  GDP: { name: 'Gross Domestic Product', unit: '%', frequency: 'Quarterly' },
  CPI: { name: 'Consumer Price Index', unit: '%', frequency: 'Monthly' },
  UNEMPLOYMENT: { name: 'Unemployment Rate', unit: '%', frequency: 'Monthly' },
  INTEREST_RATE: { name: 'Fed Funds Rate', unit: '%', frequency: 'Meeting' },
  PMI: { name: 'Purchasing Managers Index', unit: 'Index', frequency: 'Monthly' },
  RETAIL_SALES: { name: 'Retail Sales', unit: '%', frequency: 'Monthly' },
  TRADE_BALANCE: { name: 'Trade Balance', unit: '$B', frequency: 'Monthly' },
};
