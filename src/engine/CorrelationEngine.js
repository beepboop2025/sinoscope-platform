/**
 * CorrelationEngine - Cross-market correlation analysis
 * Computes rolling correlations and detects regime changes
 */
import { pearsonCorrelation, buildCorrelationMatrix, rollingCorrelation, findCorrelatedPairs } from '../utils/correlation';

/**
 * Create CorrelationEngine instance
 * @returns {Object} Engine methods
 */
export function createCorrelationEngine() {
  // Store price histories for each symbol
  const priceHistory = new Map();
  const maxHistory = 252; // 1 year of daily data

  /**
   * Add price data point for a symbol
   * @param {string} symbol - Ticker symbol
   * @param {number} price - Current price
   * @param {number} timestamp - Unix timestamp
   */
  function addPrice(symbol, price, timestamp = Date.now()) {
    if (!priceHistory.has(symbol)) {
      priceHistory.set(symbol, []);
    }
    
    const history = priceHistory.get(symbol);
    history.push({ price, timestamp });
    
    // Keep only maxHistory points
    if (history.length > maxHistory) {
      history.shift();
    }
  }

  /**
   * Get correlation between two symbols
   * @param {string} symbol1 - First symbol
   * @param {string} symbol2 - Second symbol
   * @param {number} window - Lookback window
   * @returns {number|null} Correlation coefficient
   */
  function getCorrelation(symbol1, symbol2, window = 30) {
    const h1 = priceHistory.get(symbol1);
    const h2 = priceHistory.get(symbol2);
    
    if (!h1 || !h2 || h1.length < window || h2.length < window) {
      return null;
    }
    
    const prices1 = h1.slice(-window).map(p => p.price);
    const prices2 = h2.slice(-window).map(p => p.price);
    
    return pearsonCorrelation(prices1, prices2);
  }

  /**
   * Get full correlation matrix for all tracked symbols
   * @param {number} window - Lookback window
   * @returns {Object} Correlation matrix and symbols
   */
  function getCorrelationMatrix(window = 30) {
    const symbols = Array.from(priceHistory.keys());
    const data = {};
    
    symbols.forEach(sym => {
      const history = priceHistory.get(sym);
      if (history.length >= window) {
        data[sym] = history.slice(-window).map(p => p.price);
      }
    });
    
    return buildCorrelationMatrix(data);
  }

  /**
   * Get rolling correlation between two symbols
   * @param {string} symbol1 - First symbol
   * @param {string} symbol2 - Second symbol
   * @param {number} window - Rolling window
   * @returns {Array} Array of correlation values
   */
  function getRollingCorrelation(symbol1, symbol2, window = 30) {
    const h1 = priceHistory.get(symbol1);
    const h2 = priceHistory.get(symbol2);
    
    if (!h1 || !h2) return [];
    
    const minLen = Math.min(h1.length, h2.length);
    const prices1 = h1.slice(-minLen).map(p => p.price);
    const prices2 = h2.slice(-minLen).map(p => p.price);
    
    return rollingCorrelation(prices1, prices2, window);
  }

  /**
   * Find highly correlated pairs
   * @param {number} threshold - Minimum correlation
   * @param {number} window - Lookback window
   * @returns {Array} Correlated pairs
   */
  function findHighCorrelations(threshold = 0.8, window = 30) {
    const { matrix } = getCorrelationMatrix(window);
    return findCorrelatedPairs(matrix, threshold);
  }

  /**
   * Detect correlation breakdown (sudden change in correlation)
   * @param {string} symbol1 - First symbol
   * @param {string} symbol2 - Second symbol
   * @returns {Object|null} Breakdown info or null
   */
  function detectCorrelationBreakdown(symbol1, symbol2) {
    const shortWindow = 10;
    const longWindow = 60;
    
    const shortCorr = getCorrelation(symbol1, symbol2, shortWindow);
    const longCorr = getCorrelation(symbol1, symbol2, longWindow);
    
    if (shortCorr === null || longCorr === null) return null;
    
    const diff = Math.abs(shortCorr - longCorr);
    
    if (diff > 0.5) {
      return {
        symbol1,
        symbol2,
        shortCorrelation: shortCorr,
        longCorrelation: longCorr,
        change: shortCorr - longCorr,
        severity: diff > 0.7 ? 'high' : 'medium',
        timestamp: Date.now(),
      };
    }
    
    return null;
  }

  /**
   * Get all tracked symbols
   * @returns {Array} Symbol list
   */
  function getSymbols() {
    return Array.from(priceHistory.keys());
  }

  /**
   * Clear all data
   */
  function clear() {
    priceHistory.clear();
  }

  return {
    addPrice,
    getCorrelation,
    getCorrelationMatrix,
    getRollingCorrelation,
    findHighCorrelations,
    detectCorrelationBreakdown,
    getSymbols,
    clear,
  };
}

export default createCorrelationEngine;
