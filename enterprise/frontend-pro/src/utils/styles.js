// Tailwind utility for conditional class merging
export const clsx = (...classes) => {
  return classes.filter(Boolean).join(' ');
};

// Tailwind class merger (simplified version of tailwind-merge)
export const tw = (...classes) => {
  return classes.filter(Boolean).join(' ');
};

// Format price with proper decimals
export const formatPrice = (price, decimals = 2) => {
  if (price === null || price === undefined) return '-';
  return price.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

// Format large numbers
export const formatNumber = (num, compact = false) => {
  if (num === null || num === undefined) return '-';
  if (compact && num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
  if (compact && num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
  if (compact && num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
  return num.toLocaleString('en-US');
};

// Format percentage
export const formatPercent = (value, decimals = 2) => {
  if (value === null || value === undefined) return '-';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
};

// Get color for value
export const getValueColor = (value, zeroIsGood = false) => {
  if (value === null || value === undefined) return 'text-slate-400';
  if (value === 0) return zeroIsGood ? 'text-green-400' : 'text-slate-400';
  return value > 0 ? 'text-green-400' : 'text-red-400';
};

// Generate random chart data for demo
export const generateChartData = (count = 200, startPrice = 150) => {
  const data = [];
  let price = startPrice;
  const now = new Date();
  
  for (let i = count; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 86400000 / 24);
    const volatility = 0.02;
    const change = (Math.random() - 0.5) * volatility * price;
    
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * volatility * price * 0.5;
    const low = Math.min(open, close) - Math.random() * volatility * price * 0.5;
    const volume = Math.floor(Math.random() * 1000000) + 500000;
    
    data.push({
      time: time.toISOString().split('T')[0],
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume,
    });
    
    price = close;
  }
  
  return data;
};

// Calculate SMA
export const calculateSMA = (data, period) => {
  const sma = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    sma.push({
      time: data[i].time,
      value: sum / period,
    });
  }
  return sma;
};

// Calculate EMA
export const calculateEMA = (data, period) => {
  const ema = [];
  const multiplier = 2 / (period + 1);
  
  let emaValue = data[0].close;
  ema.push({ time: data[0].time, value: emaValue });
  
  for (let i = 1; i < data.length; i++) {
    emaValue = (data[i].close - emaValue) * multiplier + emaValue;
    ema.push({
      time: data[i].time,
      value: emaValue,
    });
  }
  
  return ema;
};

// Calculate Bollinger Bands
export const calculateBollinger = (data, period = 20, stdDev = 2) => {
  const bands = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const mean = slice.reduce((sum, d) => sum + d.close, 0) / period;
    const variance = slice.reduce((sum, d) => sum + Math.pow(d.close - mean, 2), 0) / period;
    const sd = Math.sqrt(variance);
    
    bands.push({
      time: data[i].time,
      upper: mean + stdDev * sd,
      middle: mean,
      lower: mean - stdDev * sd,
    });
  }
  return bands;
};

// Calculate RSI
export const calculateRSI = (data, period = 14) => {
  const rsi = [];
  let gains = 0;
  let losses = 0;
  
  for (let i = 1; i <= period; i++) {
    const change = data[i].close - data[i - 1].close;
    if (change > 0) gains += change;
    else losses -= change;
  }
  
  let avgGain = gains / period;
  let avgLoss = losses / period;
  
  for (let i = period; i < data.length; i++) {
    const change = data[i].close - data[i - 1].close;
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    
    const rs = avgGain / avgLoss;
    const rsiValue = 100 - (100 / (1 + rs));
    
    rsi.push({
      time: data[i].time,
      value: rsiValue,
    });
  }
  
  return rsi;
};

// Calculate MACD
export const calculateMACD = (data, fast = 12, slow = 26, signal = 9) => {
  const fastEMA = calculateEMA(data, fast);
  const slowEMA = calculateEMA(data, slow);
  
  const macd = [];
  for (let i = slow - 1; i < data.length; i++) {
    macd.push({
      time: data[i].time,
      value: fastEMA[i].value - slowEMA[i].value,
    });
  }
  
  const signalLine = calculateEMA(macd.map(d => ({ close: d.value, time: d.time })), signal);
  
  return macd.map((m, i) => ({
    time: m.time,
    macd: m.value,
    signal: signalLine[i]?.value || 0,
    histogram: m.value - (signalLine[i]?.value || 0),
  }));
};

// Convert to Heikin-Ashi
export const toHeikinAshi = (data) => {
  const ha = [];
  let prevHA = null;
  
  for (const candle of data) {
    const close = (candle.open + candle.high + candle.low + candle.close) / 4;
    const open = prevHA ? (prevHA.open + prevHA.close) / 2 : (candle.open + candle.close) / 2;
    const high = Math.max(candle.high, open, close);
    const low = Math.min(candle.low, open, close);
    
    const haCandle = {
      time: candle.time,
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume: candle.volume,
    };
    
    ha.push(haCandle);
    prevHA = haCandle;
  }
  
  return ha;
};
