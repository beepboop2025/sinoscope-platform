/**
 * CorrelationEngine - Cross-market correlation analysis
 * Computes rolling correlations and detects regime changes
 */
import { pearsonCorrelation, buildCorrelationMatrix, rollingCorrelation, findCorrelatedPairs } from '../utils/correlation';
import type { CorrelationMatrix, CorrelatedPair } from '../types/engine';

interface PricePoint {
  price: number;
  timestamp: number;
}

interface CorrelationBreakdown {
  symbol1: string;
  symbol2: string;
  shortCorrelation: number;
  longCorrelation: number;
  change: number;
  severity: 'high' | 'medium';
  timestamp: number;
}

interface CorrelationEngineInstance {
  addPrice(symbol: string, price: number, timestamp?: number): void;
  getCorrelation(symbol1: string, symbol2: string, window?: number): number | null;
  getCorrelationMatrix(window?: number): ReturnType<typeof buildCorrelationMatrix>;
  getRollingCorrelation(symbol1: string, symbol2: string, window?: number): number[];
  findHighCorrelations(threshold?: number, window?: number): ReturnType<typeof findCorrelatedPairs>;
  detectCorrelationBreakdown(symbol1: string, symbol2: string): CorrelationBreakdown | null;
  getSymbols(): string[];
  clear(): void;
}

/**
 * Create CorrelationEngine instance
 */
export function createCorrelationEngine(): CorrelationEngineInstance {
  // Store price histories for each symbol
  const priceHistory = new Map<string, PricePoint[]>();
  const maxHistory = 252; // 1 year of daily data

  /**
   * Add price data point for a symbol
   */
  function addPrice(symbol: string, price: number, timestamp: number = Date.now()): void {
    if (!priceHistory.has(symbol)) {
      priceHistory.set(symbol, []);
    }

    const history = priceHistory.get(symbol)!;
    history.push({ price, timestamp });

    // Keep only maxHistory points
    if (history.length > maxHistory) {
      history.shift();
    }
  }

  /**
   * Get correlation between two symbols
   */
  function getCorrelation(symbol1: string, symbol2: string, window: number = 30): number | null {
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
   */
  function getCorrelationMatrix(window: number = 30): ReturnType<typeof buildCorrelationMatrix> {
    const symbols = Array.from(priceHistory.keys());
    const data: Record<string, number[]> = {};

    symbols.forEach(sym => {
      const history = priceHistory.get(sym)!;
      if (history.length >= window) {
        data[sym] = history.slice(-window).map(p => p.price);
      }
    });

    return buildCorrelationMatrix(data);
  }

  /**
   * Get rolling correlation between two symbols
   */
  function getRollingCorrelation(symbol1: string, symbol2: string, window: number = 30): number[] {
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
   */
  function findHighCorrelations(threshold: number = 0.8, window: number = 30): ReturnType<typeof findCorrelatedPairs> {
    const { matrix } = getCorrelationMatrix(window);
    return findCorrelatedPairs(matrix, threshold);
  }

  /**
   * Detect correlation breakdown (sudden change in correlation)
   */
  function detectCorrelationBreakdown(symbol1: string, symbol2: string): CorrelationBreakdown | null {
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
   */
  function getSymbols(): string[] {
    return Array.from(priceHistory.keys());
  }

  /**
   * Clear all data
   */
  function clear(): void {
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
