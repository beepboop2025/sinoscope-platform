/**
 * TechnicalEngine - Technical indicator calculations
 * Computes indicators for price analysis
 */
import { sma, ema, rsi, macd, bollingerBands, roc, atr, detectLevels } from '../utils/technicals';

/**
 * Create TechnicalEngine instance
 * @returns {Object} Engine methods
 */
export function createTechnicalEngine() {
  // Store OHLCV data for each symbol
  const ohlcvData = new Map();
  const maxHistory = 500;

  /**
   * Add OHLCV data point
   * @param {string} symbol - Ticker symbol
   * @param {Object} data - { open, high, low, close, volume, timestamp }
   */
  function addCandle(symbol, data) {
    if (!ohlcvData.has(symbol)) {
      ohlcvData.set(symbol, []);
    }
    
    const history = ohlcvData.get(symbol);
    history.push(data);
    
    if (history.length > maxHistory) {
      history.shift();
    }
  }

  /**
   * Get indicator values for a symbol
   * @param {string} symbol - Ticker symbol
   * @returns {Object|null} All indicators
   */
  function getIndicators(symbol) {
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
   * @param {string} symbol - Ticker symbol
   * @returns {Object|null} Trend info
   */
  function getTrend(symbol) {
    const history = ohlcvData.get(symbol);
    if (!history || history.length < 50) return null;
    
    const closes = history.map(c => c.close);
    const current = closes[closes.length - 1];
    
    const sma20 = sma(closes, 20).slice(-1)[0];
    const sma50 = sma(closes, 50).slice(-1)[0];
    
    let trend = 'neutral';
    let strength = 0;
    
    if (current > sma20 && sma20 > sma50) {
      trend = 'bullish';
      strength = (current - sma50) / sma50;
    } else if (current < sma20 && sma20 < sma50) {
      trend = 'bearish';
      strength = (sma50 - current) / sma50;
    }
    
    return {
      symbol,
      trend,
      strength: strength * 100, // as percentage
      sma20,
      sma50,
      current,
    };
  }

  /**
   * Generate trading signals
   * @param {string} symbol - Ticker symbol
   * @returns {Array} Signal list
   */
  function getSignals(symbol) {
    const history = ohlcvData.get(symbol);
    if (!history || history.length < 50) return [];
    
    const closes = history.map(c => c.close);
    const signals = [];
    
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
   * @param {string} symbol - Ticker symbol
   * @param {number} window - Lookback window
   * @returns {Object|null} Volatility data
   */
  function getVolatility(symbol, window = 20) {
    const history = ohlcvData.get(symbol);
    if (!history || history.length < window) return null;
    
    const closes = history.slice(-window).map(c => c.close);
    const highs = history.slice(-window).map(c => c.high);
    const lows = history.slice(-window).map(c => c.low);
    
    // Calculate daily returns
    const returns = [];
    for (let i = 1; i < closes.length; i++) {
      returns.push((closes[i] - closes[i - 1]) / closes[i - 1]);
    }
    
    // Standard deviation of returns (volatility)
    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
    const volatility = Math.sqrt(variance) * Math.sqrt(252) * 100; // Annualized %
    
    const bb = bollingerBands(closes);
    const currentATR = atr(highs, lows, closes, 14).slice(-1)[0];
    
    return {
      symbol,
      annualizedVolatility: volatility,
      atr: currentATR,
      bbWidth: ((bb.upper[bb.upper.length - 1] - bb.lower[bb.lower.length - 1]) / closes[closes.length - 1]) * 100,
      timestamp: Date.now(),
    };
  }

  /**
   * Clear symbol data
   * @param {string} symbol - Ticker symbol (optional, clears all if omitted)
   */
  function clear(symbol) {
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
