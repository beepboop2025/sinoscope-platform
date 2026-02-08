/**
 * Technical Indicator Utilities
 * Pure functions for technical analysis (SMA, EMA, RSI, MACD, Bollinger)
 */

/**
 * Simple Moving Average (SMA)
 * @param {Array<number>} data - Price data
 * @param {number} period - SMA period
 * @returns {Array<number>} SMA values
 */
export function sma(data, period) {
  const result = [];
  for (let i = period - 1; i < data.length; i++) {
    const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
    result.push(+(sum / period).toFixed(4));
  }
  return result;
}

/**
 * Exponential Moving Average (EMA)
 * @param {Array<number>} data - Price data
 * @param {number} period - EMA period
 * @returns {Array<number>} EMA values
 */
export function ema(data, period) {
  const k = 2 / (period + 1);
  const result = [data[0]];
  
  for (let i = 1; i < data.length; i++) {
    const emaValue = data[i] * k + result[i - 1] * (1 - k);
    result.push(+emaValue.toFixed(4));
  }
  
  return result;
}

/**
 * Relative Strength Index (RSI)
 * @param {Array<number>} data - Price data
 * @param {number} period - RSI period (default 14)
 * @returns {Array<number>} RSI values (0-100)
 */
export function rsi(data, period = 14) {
  if (data.length < period + 1) return [];
  
  const changes = [];
  for (let i = 1; i < data.length; i++) {
    changes.push(data[i] - data[i - 1]);
  }
  
  const result = [];
  let avgGain = 0;
  let avgLoss = 0;
  
  // Initial averages
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) avgGain += changes[i];
    else avgLoss += Math.abs(changes[i]);
  }
  avgGain /= period;
  avgLoss /= period;
  
  // First RSI
  let rs = avgGain / avgLoss;
  result.push(+(100 - 100 / (1 + rs)).toFixed(2));
  
  // Remaining RSI values
  for (let i = period; i < changes.length; i++) {
    const gain = changes[i] > 0 ? changes[i] : 0;
    const loss = changes[i] < 0 ? Math.abs(changes[i]) : 0;
    
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    
    rs = avgGain / avgLoss;
    result.push(+(100 - 100 / (1 + rs)).toFixed(2));
  }
  
  return result;
}

/**
 * MACD (Moving Average Convergence Divergence)
 * @param {Array<number>} data - Price data
 * @param {number} fast - Fast EMA period (default 12)
 * @param {number} slow - Slow EMA period (default 26)
 * @param {number} signal - Signal line period (default 9)
 * @returns {Object} MACD line, signal line, histogram
 */
export function macd(data, fast = 12, slow = 26, signal = 9) {
  const emaFast = ema(data, fast);
  const emaSlow = ema(data, slow);
  
  // MACD line = Fast EMA - Slow EMA
  const macdLine = [];
  const offset = slow - fast;
  for (let i = 0; i < emaSlow.length; i++) {
    macdLine.push(+(emaFast[i + offset] - emaSlow[i]).toFixed(4));
  }
  
  // Signal line = EMA of MACD
  const signalLine = ema(macdLine, signal);
  
  // Histogram = MACD - Signal
  const histogram = [];
  const signalOffset = macdLine.length - signalLine.length;
  for (let i = 0; i < signalLine.length; i++) {
    histogram.push(+(macdLine[i + signalOffset] - signalLine[i]).toFixed(4));
  }
  
  return { macdLine, signalLine, histogram };
}

/**
 * Bollinger Bands
 * @param {Array<number>} data - Price data
 * @param {number} period - SMA period (default 20)
 * @param {number} multiplier - Std dev multiplier (default 2)
 * @returns {Object} Upper band, middle band (SMA), lower band
 */
export function bollingerBands(data, period = 20, multiplier = 2) {
  const middle = sma(data, period);
  const upper = [];
  const lower = [];
  
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / period;
    const stdDev = Math.sqrt(variance);
    
    upper.push(+(mean + multiplier * stdDev).toFixed(4));
    lower.push(+(mean - multiplier * stdDev).toFixed(4));
  }
  
  return { upper, middle, lower };
}

/**
 * Rate of Change (ROC)
 * @param {Array<number>} data - Price data
 * @param {number} period - Period (default 12)
 * @returns {Array<number>} ROC percentages
 */
export function roc(data, period = 12) {
  const result = [];
  for (let i = period; i < data.length; i++) {
    const change = ((data[i] - data[i - period]) / data[i - period]) * 100;
    result.push(+change.toFixed(2));
  }
  return result;
}

/**
 * Stochastic Oscillator
 * @param {Array<number>} high - High prices
 * @param {Array<number>} low - Low prices
 * @param {Array<number>} close - Close prices
 * @param {number} kPeriod - %K period (default 14)
 * @param {number} dPeriod - %D period (default 3)
 * @returns {Object} %K and %D lines
 */
export function stochastic(high, low, close, kPeriod = 14, dPeriod = 3) {
  const kValues = [];
  
  for (let i = kPeriod - 1; i < close.length; i++) {
    const highestHigh = Math.max(...high.slice(i - kPeriod + 1, i + 1));
    const lowestLow = Math.min(...low.slice(i - kPeriod + 1, i + 1));
    
    if (highestHigh === lowestLow) {
      kValues.push(50);
    } else {
      kValues.push(+((close[i] - lowestLow) / (highestHigh - lowestLow) * 100).toFixed(2));
    }
  }
  
  // %D = SMA of %K
  const dValues = sma(kValues, dPeriod);
  
  return { k: kValues, d: dValues };
}

/**
 * Average True Range (ATR)
 * @param {Array<number>} high - High prices
 * @param {Array<number>} low - Low prices
 * @param {Array<number>} close - Close prices
 * @param {number} period - ATR period (default 14)
 * @returns {Array<number>} ATR values
 */
export function atr(high, low, close, period = 14) {
  const trValues = [high[0] - low[0]]; // First TR
  
  for (let i = 1; i < close.length; i++) {
    const tr1 = high[i] - low[i];
    const tr2 = Math.abs(high[i] - close[i - 1]);
    const tr3 = Math.abs(low[i] - close[i - 1]);
    trValues.push(Math.max(tr1, tr2, tr3));
  }
  
  return sma(trValues, period);
}

/**
 * Fibonacci Retracement levels
 * @param {number} high - High price
 * @param {number} low - Low price
 * @returns {Object} Fibonacci levels
 */
export function fibonacciLevels(high, low) {
  const diff = high - low;
  return {
    '0%': high,
    '23.6%': +(high - diff * 0.236).toFixed(4),
    '38.2%': +(high - diff * 0.382).toFixed(4),
    '50%': +(high - diff * 0.5).toFixed(4),
    '61.8%': +(high - diff * 0.618).toFixed(4),
    '78.6%': +(high - diff * 0.786).toFixed(4),
    '100%': low,
  };
}

/**
 * Detect price patterns (simple support/resistance)
 * @param {Array<number>} data - Price data
 * @param {number} window - Lookback window (default 5)
 * @returns {Object} Support and resistance levels
 */
export function detectLevels(data, window = 5) {
  const supports = [];
  const resistances = [];
  
  for (let i = window; i < data.length - window; i++) {
    const slice = data.slice(i - window, i + window + 1);
    const current = data[i];
    
    // Local minimum
    if (current === Math.min(...slice)) {
      supports.push({ price: current, index: i });
    }
    
    // Local maximum
    if (current === Math.max(...slice)) {
      resistances.push({ price: current, index: i });
    }
  }
  
  return { supports, resistances };
}

export default {
  sma,
  ema,
  rsi,
  macd,
  bollingerBands,
  roc,
  stochastic,
  atr,
  fibonacciLevels,
  detectLevels,
};
