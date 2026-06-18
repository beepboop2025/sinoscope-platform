/**
 * TechnicalEngine - Technical indicator calculations
 * Computes indicators for price analysis
 */
import { sma, ema, rsi, macd, bollingerBands, roc, atr, detectLevels } from '../utils/technicals';

interface OHLCVCandle {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: number;
}

interface IndicatorResult {
  symbol: string;
  timestamp: number;
  sma20: number;
  sma50: number;
  sma200: number | null;
  ema12: number;
  ema26: number;
  rsi14: number;
  macd: ReturnType<typeof macd>;
  roc12: number;
  bollinger: ReturnType<typeof bollingerBands>;
  atr14: number;
  levels: ReturnType<typeof detectLevels>;
}

interface TrendResult {
  symbol: string;
  trend: string;
  strength: number;
  sma20: number;
  sma50: number;
  current: number;
}

interface TechSignal {
  type: string;
  indicator: string;
  value: number;
  strength: string;
}

interface VolatilityResult {
  symbol: string;
  annualizedVolatility: number;
  atr: number;
  bbWidth: number;
  timestamp: number;
}

interface TechnicalEngineInstance {
  addCandle(symbol: string, data: OHLCVCandle): void;
  getIndicators(symbol: string): IndicatorResult | null;
  getTrend(symbol: string): TrendResult | null;
  getSignals(symbol: string): TechSignal[];
  getVolatility(symbol: string, window?: number): VolatilityResult | null;
  clear(symbol?: string): void;
}

/**
 * Create TechnicalEngine instance
 */
export function createTechnicalEngine(): TechnicalEngineInstance {
  // Store OHLCV data for each symbol
  const ohlcvData = new Map<string, OHLCVCandle[]>();
  const maxHistory = 500;

  /**
   * Add OHLCV data point
   */
  function addCandle(symbol: string, data: OHLCVCandle): void {
    if (!ohlcvData.has(symbol)) {
      ohlcvData.set(symbol, []);
    }

    const history = ohlcvData.get(symbol)!;
    history.push(data);

    if (history.length > maxHistory) {
      history.shift();
    }
  }

  /**
   * Get indicator values for a symbol
   */
  function getIndicators(symbol: string): IndicatorResult | null {
    const history = ohlcvData.get(symbol);
    if (!history || history.length < 50) return null;

    const closes = history.map(c => c.close);
    const highs = history.map(c => c.high);
    const lows = history.map(c => c.low);

    return {
      symbol,
      timestamp: Date.now(),

      // Trend indicators
      sma20: sma(closes, 20).slice(-1)[0],
      sma50: sma(closes, 50).slice(-1)[0],
      sma200: closes.length >= 200 ? sma(closes, 200).slice(-1)[0] : null,
      ema12: ema(closes, 12).slice(-1)[0],
      ema26: ema(closes, 26).slice(-1)[0],

      // Momentum indicators
      rsi14: rsi(closes, 14).slice(-1)[0],
      macd: macd(closes),
      roc12: roc(closes, 12).slice(-1)[0],

      // Volatility indicators
      bollinger: bollingerBands(closes),
      atr14: atr(highs, lows, closes, 14).slice(-1)[0],

      // Support/Resistance
      levels: detectLevels(closes, 5),
    };
  }

  /**
   * Get trend analysis
   */
  function getTrend(symbol: string): TrendResult | null {
    const history = ohlcvData.get(symbol);
    if (!history || history.length < 50) return null;

    const closes = history.map(c => c.close);
    const current = closes[closes.length - 1];

    const sma20Val = sma(closes, 20).slice(-1)[0];
    const sma50Val = sma(closes, 50).slice(-1)[0];

    let trend = 'neutral';
    let strength = 0;

    if (current > sma20Val && sma20Val > sma50Val) {
      trend = 'bullish';
      strength = (current - sma50Val) / sma50Val;
    } else if (current < sma20Val && sma20Val < sma50Val) {
      trend = 'bearish';
      strength = (sma50Val - current) / sma50Val;
    }

    return {
      symbol,
      trend,
      strength: strength * 100, // as percentage
      sma20: sma20Val,
      sma50: sma50Val,
      current,
    };
  }

  /**
   * Generate trading signals
   */
  function getSignals(symbol: string): TechSignal[] {
    const history = ohlcvData.get(symbol);
    if (!history || history.length < 50) return [];

    const closes = history.map(c => c.close);
    const signals: TechSignal[] = [];

    // RSI signals
    const rsiValues = rsi(closes, 14);
    const currentRSI = rsiValues[rsiValues.length - 1];

    if (currentRSI < 30) {
      signals.push({ type: 'oversold', indicator: 'RSI', value: currentRSI, strength: 'high' });
    } else if (currentRSI > 70) {
      signals.push({ type: 'overbought', indicator: 'RSI', value: currentRSI, strength: 'high' });
    }

    // MACD signals
    const macdData = macd(closes);
    const histogram = macdData.histogram;
    const prevHist = histogram[histogram.length - 2];
    const currHist = histogram[histogram.length - 1];

    if (prevHist < 0 && currHist > 0) {
      signals.push({ type: 'bullish_crossover', indicator: 'MACD', value: currHist, strength: 'medium' });
    } else if (prevHist > 0 && currHist < 0) {
      signals.push({ type: 'bearish_crossover', indicator: 'MACD', value: currHist, strength: 'medium' });
    }

    // Bollinger Band signals
    const bb = bollingerBands(closes);
    const current = closes[closes.length - 1];
    const upper = bb.upper[bb.upper.length - 1];
    const lower = bb.lower[bb.lower.length - 1];

    if (current > upper) {
      signals.push({ type: 'above_upper_band', indicator: 'Bollinger', value: current, strength: 'low' });
    } else if (current < lower) {
      signals.push({ type: 'below_lower_band', indicator: 'Bollinger', value: current, strength: 'low' });
    }

    return signals;
  }

  /**
   * Get volatility metrics
   */
  function getVolatility(symbol: string, window: number = 20): VolatilityResult | null {
    const history = ohlcvData.get(symbol);
    if (!history || history.length < window) return null;

    const closes = history.slice(-window).map(c => c.close);
    const highs = history.slice(-window).map(c => c.high);
    const lows = history.slice(-window).map(c => c.low);

    // Calculate daily returns
    const returns: number[] = [];
    for (let i = 1; i < closes.length; i++) {
      returns.push((closes[i] - closes[i - 1]) / closes[i - 1]);
    }

    // Standard deviation of returns (volatility)
    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
    const vol = Math.sqrt(variance) * Math.sqrt(252) * 100; // Annualized %

    const bb = bollingerBands(closes);
    const currentATR = atr(highs, lows, closes, 14).slice(-1)[0];

    return {
      symbol,
      annualizedVolatility: vol,
      atr: currentATR,
      bbWidth: ((bb.upper[bb.upper.length - 1] - bb.lower[bb.lower.length - 1]) / closes[closes.length - 1]) * 100,
      timestamp: Date.now(),
    };
  }

  /**
   * Clear symbol data
   */
  function clear(symbol?: string): void {
    if (symbol) {
      ohlcvData.delete(symbol);
    } else {
      ohlcvData.clear();
    }
  }

  return {
    addCandle,
    getIndicators,
    getTrend,
    getSignals,
    getVolatility,
    clear,
  };
}

export default createTechnicalEngine;
