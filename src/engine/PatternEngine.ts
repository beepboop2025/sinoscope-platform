/**
 * PatternEngine - Anomaly detection and pattern recognition
 * Identifies unusual market behavior and divergences
 */

interface PatternEvent {
  type: string;
  symbol?: string;
  symbols?: string[];
  severity: string;
  timestamp: number;
  message: string;
  change?: number;
  volumeRatio?: number;
  indicator?: string;
  level?: number;
  currentCorrelation?: number;
  historicalCorrelation?: number;
}

interface CorrelationPattern {
  correlations: number[];
  avgCorrelation: number;
}

interface CrossMarketAnomaly {
  type: string;
  symbols: string[];
  severity: string;
  currentCorrelation: number;
  historicalCorrelation: number;
  timestamp: number;
  message: string;
}

interface PatternEngineInstance {
  detectPriceAnomaly(symbol: string, currentPrice: number, previousPrice: number, threshold?: number): PatternEvent | null;
  detectVolumeAnomaly(symbol: string, currentVolume: number, avgVolume: number): PatternEvent | null;
  detectDivergence(symbol: string, prices: number[], indicator: number[], indicatorName: string): PatternEvent | null;
  detectBreakout(symbol: string, currentPrice: number, resistance: number, support: number): PatternEvent | null;
  detectCrossMarketAnomaly(correlations: Record<string, Record<string, number>>): CrossMarketAnomaly[];
  updateCorrelationPattern(symbol1: string, symbol2: string, correlation: number): void;
  getRecentEvents(limit?: number): PatternEvent[];
  getSymbolEvents(symbol: string): PatternEvent[];
  clear(): void;
}

/**
 * Create PatternEngine instance
 */
export function createPatternEngine(): PatternEngineInstance {
  const eventLog: PatternEvent[] = [];
  const patterns = new Map<string, CorrelationPattern>();

  /**
   * Detect price anomaly (sudden large move)
   */
  function detectPriceAnomaly(symbol: string, currentPrice: number, previousPrice: number, threshold: number = 2.5): PatternEvent | null {
    if (!previousPrice || !Number.isFinite(currentPrice) || !Number.isFinite(previousPrice)) return null;
    const change = (currentPrice - previousPrice) / previousPrice;
    const changePct = change * 100;

    // Simple anomaly detection based on percentage move
    if (Math.abs(changePct) > 5) {
      const anomaly: PatternEvent = {
        type: 'price_spike',
        symbol,
        severity: Math.abs(changePct) > 10 ? 'critical' : Math.abs(changePct) > 7 ? 'high' : 'medium',
        change: changePct,
        timestamp: Date.now(),
        message: `${symbol} moved ${changePct > 0 ? '+' : ''}${changePct.toFixed(2)}%`,
      };

      eventLog.push(anomaly);
      return anomaly;
    }

    return null;
  }

  /**
   * Detect volume anomaly
   */
  function detectVolumeAnomaly(symbol: string, currentVolume: number, avgVolume: number): PatternEvent | null {
    if (!avgVolume || !Number.isFinite(currentVolume)) return null;
    const ratio = currentVolume / avgVolume;

    if (ratio > 3) {
      const anomaly: PatternEvent = {
        type: 'volume_spike',
        symbol,
        severity: ratio > 5 ? 'high' : 'medium',
        volumeRatio: ratio,
        timestamp: Date.now(),
        message: `${symbol} volume ${ratio.toFixed(1)}x average`,
      };

      if (eventLog.length > 500) eventLog.splice(0, eventLog.length - 250);
      eventLog.push(anomaly);
      return anomaly;
    }

    return null;
  }

  /**
   * Detect divergence between price and indicator
   */
  function detectDivergence(symbol: string, prices: number[], indicator: number[], indicatorName: string): PatternEvent | null {
    if (prices.length < 20 || indicator.length < 20) return null;

    const priceWindow = prices.slice(-20);
    const indicatorWindow = indicator.slice(-20);

    // Find local highs and lows
    const priceHigh = Math.max(...priceWindow);
    const priceLow = Math.min(...priceWindow);
    const indicatorHigh = Math.max(...indicatorWindow);
    const indicatorLow = Math.min(...indicatorWindow);

    const currentPrice = priceWindow[priceWindow.length - 1];
    const currentIndicator = indicatorWindow[indicatorWindow.length - 1];

    // Bearish divergence: price higher high, indicator lower high
    if (currentPrice > priceHigh * 0.98 && currentIndicator < indicatorHigh * 0.95) {
      const divergence: PatternEvent = {
        type: 'bearish_divergence',
        symbol,
        indicator: indicatorName,
        severity: 'medium',
        timestamp: Date.now(),
        message: `${symbol} bearish divergence: price near high but ${indicatorName} weakening`,
      };

      eventLog.push(divergence);
      return divergence;
    }

    // Bullish divergence: price lower low, indicator higher low
    if (currentPrice < priceLow * 1.02 && currentIndicator > indicatorLow * 1.05) {
      const divergence: PatternEvent = {
        type: 'bullish_divergence',
        symbol,
        indicator: indicatorName,
        severity: 'medium',
        timestamp: Date.now(),
        message: `${symbol} bullish divergence: price near low but ${indicatorName} strengthening`,
      };

      eventLog.push(divergence);
      return divergence;
    }

    return null;
  }

  /**
   * Detect breakout/breakdown
   */
  function detectBreakout(symbol: string, currentPrice: number, resistance: number, support: number): PatternEvent | null {
    // Breakout above resistance
    if (resistance && currentPrice > resistance * 1.01) {
      const breakout: PatternEvent = {
        type: 'breakout',
        symbol,
        severity: 'high',
        level: resistance,
        timestamp: Date.now(),
        message: `${symbol} broke above resistance at ${resistance.toFixed(2)}`,
      };

      eventLog.push(breakout);
      return breakout;
    }

    // Breakdown below support
    if (support && currentPrice < support * 0.99) {
      const breakdown: PatternEvent = {
        type: 'breakdown',
        symbol,
        severity: 'high',
        level: support,
        timestamp: Date.now(),
        message: `${symbol} broke below support at ${support.toFixed(2)}`,
      };

      eventLog.push(breakdown);
      return breakdown;
    }

    return null;
  }

  /**
   * Detect unusual cross-market behavior
   */
  function detectCrossMarketAnomaly(correlations: Record<string, Record<string, number>>): CrossMarketAnomaly[] {
    const anomalies: CrossMarketAnomaly[] = [];

    // Check for correlation breakdowns
    const pairs = Object.keys(correlations);

    for (let i = 0; i < pairs.length; i++) {
      for (let j = i + 1; j < pairs.length; j++) {
        const corr = correlations[pairs[i]][pairs[j]];

        // Historically correlated assets now uncorrelated
        if (Math.abs(corr) < 0.2 && patterns.has(`${pairs[i]}-${pairs[j]}`)) {
          const historical = patterns.get(`${pairs[i]}-${pairs[j]}`)!;
          if (historical.avgCorrelation > 0.7) {
            anomalies.push({
              type: 'correlation_breakdown',
              symbols: [pairs[i], pairs[j]],
              severity: 'high',
              currentCorrelation: corr,
              historicalCorrelation: historical.avgCorrelation,
              timestamp: Date.now(),
              message: `${pairs[i]} and ${pairs[j]} correlation broke down`,
            });
          }
        }
      }
    }

    anomalies.forEach(a => eventLog.push(a as unknown as PatternEvent));
    return anomalies;
  }

  /**
   * Update correlation pattern for a pair
   */
  function updateCorrelationPattern(symbol1: string, symbol2: string, correlation: number): void {
    const key = `${symbol1}-${symbol2}`;
    const existing = patterns.get(key) || { correlations: [], avgCorrelation: 0 };

    existing.correlations.push(correlation);
    if (existing.correlations.length > 30) {
      existing.correlations.shift();
    }

    existing.avgCorrelation = existing.correlations.reduce((a, b) => a + b, 0) / existing.correlations.length;
    patterns.set(key, existing);
  }

  /**
   * Get recent events
   */
  function getRecentEvents(limit: number = 20): PatternEvent[] {
    return eventLog.slice(-limit).reverse();
  }

  /**
   * Get events for a symbol
   */
  function getSymbolEvents(symbol: string): PatternEvent[] {
    return eventLog.filter(e => e.symbol === symbol).reverse();
  }

  /**
   * Clear all data
   */
  function clear(): void {
    eventLog.length = 0;
    patterns.clear();
  }

  return {
    detectPriceAnomaly,
    detectVolumeAnomaly,
    detectDivergence,
    detectBreakout,
    detectCrossMarketAnomaly,
    updateCorrelationPattern,
    getRecentEvents,
    getSymbolEvents,
    clear,
  };
}

export default createPatternEngine;
