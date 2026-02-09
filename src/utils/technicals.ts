/**
 * Technical Indicator Utilities
 * Pure functions for technical analysis (SMA, EMA, RSI, MACD, Bollinger)
 */

/**
 * Simple Moving Average (SMA)
 */
export function sma(data: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
    result.push(+(sum / period).toFixed(4));
  }
  return result;
}

/**
 * Exponential Moving Average (EMA)
 */
export function ema(data: number[], period: number): number[] {
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
 */
export function rsi(data: number[], period: number = 14): number[] {
  if (data.length < period + 1) return [];

  const changes: number[] = [];
  for (let i = 1; i < data.length; i++) {
    changes.push(data[i] - data[i - 1]);
  }

  const result: number[] = [];
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

interface MACDOutput {
  macdLine: number[];
  signalLine: number[];
  histogram: number[];
}

/**
 * MACD (Moving Average Convergence Divergence)
 */
export function macd(data: number[], fast: number = 12, slow: number = 26, signal: number = 9): MACDOutput {
  const emaFast = ema(data, fast);
  const emaSlow = ema(data, slow);

  // MACD line = Fast EMA - Slow EMA
  const macdLine: number[] = [];
  const offset = slow - fast;
  for (let i = 0; i < emaSlow.length; i++) {
    macdLine.push(+(emaFast[i + offset] - emaSlow[i]).toFixed(4));
  }

  // Signal line = EMA of MACD
  const signalLine = ema(macdLine, signal);

  // Histogram = MACD - Signal
  const histogram: number[] = [];
  const signalOffset = macdLine.length - signalLine.length;
  for (let i = 0; i < signalLine.length; i++) {
    histogram.push(+(macdLine[i + signalOffset] - signalLine[i]).toFixed(4));
  }

  return { macdLine, signalLine, histogram };
}

interface BollingerOutput {
  upper: number[];
  middle: number[];
  lower: number[];
}

/**
 * Bollinger Bands
 */
export function bollingerBands(data: number[], period: number = 20, multiplier: number = 2): BollingerOutput {
  const middle = sma(data, period);
  const upper: number[] = [];
  const lower: number[] = [];

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
 */
export function roc(data: number[], period: number = 12): number[] {
  const result: number[] = [];
  for (let i = period; i < data.length; i++) {
    const change = ((data[i] - data[i - period]) / data[i - period]) * 100;
    result.push(+change.toFixed(2));
  }
  return result;
}

/**
 * Average True Range (ATR)
 */
export function atr(high: number[], low: number[], close: number[], period: number = 14): number[] {
  const trValues: number[] = [high[0] - low[0]]; // First TR

  for (let i = 1; i < close.length; i++) {
    const tr1 = high[i] - low[i];
    const tr2 = Math.abs(high[i] - close[i - 1]);
    const tr3 = Math.abs(low[i] - close[i - 1]);
    trValues.push(Math.max(tr1, tr2, tr3));
  }

  return sma(trValues, period);
}

interface PriceLevel {
  price: number;
  index: number;
}

interface DetectedLevels {
  supports: PriceLevel[];
  resistances: PriceLevel[];
}

/**
 * Detect price patterns (simple support/resistance)
 */
export function detectLevels(data: number[], window: number = 5): DetectedLevels {
  const supports: PriceLevel[] = [];
  const resistances: PriceLevel[] = [];

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
  atr,
  detectLevels,
};
