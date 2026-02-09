/**
 * Feature engineering pipeline for market data.
 * Extracts numerical features from raw market snapshots for ML models.
 */

import { normalize, movingAverage, rsi, zScore, fisherYatesShuffle } from './NeuralNet.js';

// Rolling window buffer for time-series features
export class RollingBuffer {
  constructor(maxLen = 100) {
    this.maxLen = maxLen;
    this.data = {};
  }

  push(key, value) {
    if (!this.data[key]) this.data[key] = [];
    this.data[key].push(value);
    if (this.data[key].length > this.maxLen) {
      this.data[key].shift();
    }
  }

  get(key) {
    return this.data[key] || [];
  }

  len(key) {
    return (this.data[key] || []).length;
  }

  last(key, n = 1) {
    const arr = this.data[key] || [];
    return arr.slice(-n);
  }

  clear() {
    this.data = {};
  }
}

// Compute MACD (Moving Average Convergence Divergence)
function macd(prices, fast = 12, slow = 26, signal = 9) {
  if (prices.length < slow + signal) return { macd: 0, signal: 0, histogram: 0 };
  const emaFast = ema(prices, fast);
  const emaSlow = ema(prices, slow);
  const macdLine = emaFast - emaSlow;
  // Approximate signal as simple average of recent MACD values
  return { macd: macdLine, signal: macdLine * 0.8, histogram: macdLine * 0.2 };
}

// Exponential moving average (last value)
function ema(data, period) {
  if (data.length === 0) return 0;
  const k = 2 / (period + 1);
  let val = data[0];
  for (let i = 1; i < data.length; i++) {
    val = data[i] * k + val * (1 - k);
  }
  return val;
}

// Bollinger band position (where is price relative to bands)
function bollingerPosition(prices, period = 20) {
  if (prices.length < period) return 0.5;
  const recent = prices.slice(-period);
  const mean = recent.reduce((a, b) => a + b, 0) / period;
  const std = Math.sqrt(recent.reduce((a, b) => a + (b - mean) ** 2, 0) / period);
  if (std === 0) return 0.5;
  const upper = mean + 2 * std;
  const lower = mean - 2 * std;
  const current = prices[prices.length - 1];
  return Math.max(0, Math.min(1, (current - lower) / (upper - lower)));
}

// Volume ratio (current vs average)
function volumeRatio(volumes, period = 20) {
  if (volumes.length < 2) return 1;
  const recent = volumes.slice(-period);
  const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
  return avg > 0 ? volumes[volumes.length - 1] / avg : 1;
}

// Price momentum (rate of change)
function momentum(prices, period = 10) {
  if (prices.length < period + 1) return 0;
  const current = prices[prices.length - 1];
  const past = prices[prices.length - 1 - period];
  return past !== 0 ? (current - past) / past : 0;
}

// Volatility (standard deviation of returns)
function volatility(prices, period = 20) {
  if (prices.length < period + 1) return 0;
  const returns = [];
  const recent = prices.slice(-period - 1);
  for (let i = 1; i < recent.length; i++) {
    returns.push(recent[i - 1] !== 0 ? (recent[i] - recent[i - 1]) / recent[i - 1] : 0);
  }
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  return Math.sqrt(returns.reduce((a, b) => a + (b - mean) ** 2, 0) / returns.length);
}

/**
 * Extract features for a single asset from its price history.
 * Returns a fixed-size feature vector.
 */
export function extractAssetFeatures(priceHistory, volumeHistory = []) {
  const prices = priceHistory || [];
  const volumes = volumeHistory.length > 0 ? volumeHistory : new Array(prices.length).fill(1);

  if (prices.length < 5) {
    return new Array(12).fill(0);
  }

  const currentPrice = prices[prices.length - 1];
  const ma5 = movingAverage(prices, 5);
  const ma20 = movingAverage(prices, 20);

  const features = [
    // 0: RSI (normalized 0-1)
    rsi(prices, 14) / 100,
    // 1: MACD histogram (clamped)
    Math.max(-1, Math.min(1, macd(prices).histogram * 10)),
    // 2: Bollinger band position (0-1)
    bollingerPosition(prices),
    // 3: Price momentum 5-period
    Math.max(-1, Math.min(1, momentum(prices, 5) * 10)),
    // 4: Price momentum 20-period
    Math.max(-1, Math.min(1, momentum(prices, 20) * 10)),
    // 5: Volume ratio
    Math.max(0, Math.min(3, volumeRatio(volumes))),
    // 6: Volatility (clamped)
    Math.min(1, volatility(prices) * 100),
    // 7: MA5 vs MA20 crossover signal
    ma20[ma20.length - 1] !== 0 ? Math.max(-1, Math.min(1, (ma5[ma5.length - 1] - ma20[ma20.length - 1]) / ma20[ma20.length - 1] * 100)) : 0,
    // 8: Price relative to MA20
    ma20[ma20.length - 1] !== 0 ? Math.max(-1, Math.min(1, (currentPrice - ma20[ma20.length - 1]) / ma20[ma20.length - 1] * 10)) : 0,
    // 9: Recent return (1-period)
    prices.length >= 2 ? Math.max(-1, Math.min(1, (currentPrice - prices[prices.length - 2]) / (prices[prices.length - 2] || 1) * 100)) : 0,
    // 10: High-low range (if available from price data)
    prices.length >= 20 ? Math.min(1, (Math.max(...prices.slice(-20)) - Math.min(...prices.slice(-20))) / (currentPrice || 1)) : 0,
    // 11: Trend strength (slope of linear regression on recent prices)
    trendStrength(prices.slice(-20)),
  ];

  // Sanitize: replace NaN/Infinity with 0
  for (let i = 0; i < features.length; i++) {
    if (!Number.isFinite(features[i])) {
      features[i] = 0;
    }
  }

  return features;
}

// Linear regression slope normalized as trend strength
function trendStrength(prices) {
  const n = prices.length;
  if (n < 3) return 0;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += i;
    sumY += prices[i];
    sumXY += i * prices[i];
    sumX2 += i * i;
  }
  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return 0;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const avgPrice = sumY / n;
  return avgPrice !== 0 ? Math.max(-1, Math.min(1, slope / avgPrice * n)) : 0;
}

/**
 * Extract cross-market features from the full market snapshot.
 * These capture correlations between asset classes.
 */
export function extractCrossMarketFeatures(marketData) {
  if (!marketData) return new Array(8).fill(0);

  const features = [];

  // 0: BTC dominance proxy — BTC change vs overall crypto average
  const crypto = marketData.crypto || {};
  const cryptoEntries = Object.entries(crypto);
  const btcChange = crypto.BTC?.changePct || crypto.BTCUSDT?.changePct || 0;
  const avgCryptoChange = cryptoEntries.length > 0
    ? cryptoEntries.reduce((s, [, d]) => s + (Number(d?.changePct) || 0), 0) / cryptoEntries.length
    : 0;
  features.push(Math.max(-1, Math.min(1, (btcChange - avgCryptoChange) / 10)));

  // 1: Stock market breadth — % of stocks positive
  const stocks = marketData.stocks || {};
  const stockEntries = Object.entries(stocks);
  const positiveStocks = stockEntries.filter(([, d]) => (Number(d?.changePct) || 0) > 0).length;
  features.push(stockEntries.length > 0 ? positiveStocks / stockEntries.length : 0.5);

  // 2: USD strength — average forex change (inverse since pairs are usually X/USD)
  const forex = marketData.forex || {};
  const forexEntries = Object.entries(forex);
  const avgForexChange = forexEntries.length > 0
    ? forexEntries.reduce((s, [, d]) => s + (typeof d === 'number' ? 0 : Number(d?.changePct) || 0), 0) / forexEntries.length
    : 0;
  features.push(Math.max(-1, Math.min(1, -avgForexChange / 5)));

  // 3: Bond yield direction — average bond change
  const bonds = marketData.bonds || [];
  const bondArr = Array.isArray(bonds) ? bonds : Object.entries(bonds).map(([k, v]) => ({ maturity: k, ...(typeof v === 'number' ? { yield: v } : v) }));
  const avgBondChange = bondArr.length > 0
    ? bondArr.reduce((s, b) => s + (Number(b?.change) || 0), 0) / bondArr.length
    : 0;
  features.push(Math.max(-1, Math.min(1, avgBondChange / 0.1)));

  // 4: Commodity strength
  const commodities = marketData.commodities || {};
  const commEntries = Object.entries(commodities);
  const avgCommChange = commEntries.length > 0
    ? commEntries.reduce((s, [, d]) => s + (typeof d === 'number' ? 0 : Number(d?.changePct) || 0), 0) / commEntries.length
    : 0;
  features.push(Math.max(-1, Math.min(1, avgCommChange / 5)));

  // 5: Risk-on/risk-off indicator (stocks positive + crypto positive = risk on)
  const avgStockChange = stockEntries.length > 0
    ? stockEntries.reduce((s, [, d]) => s + (Number(d?.changePct) || 0), 0) / stockEntries.length
    : 0;
  const riskOn = (avgStockChange > 0 && avgCryptoChange > 0) ? 1 : (avgStockChange < 0 && avgCryptoChange < 0) ? -1 : 0;
  features.push(riskOn);

  // 6: Crypto-stock correlation proxy
  features.push(Math.max(-1, Math.min(1, (avgCryptoChange * avgStockChange) / 25)));

  // 7: Overall market volatility (dispersion of changes)
  const allChanges = [
    ...stockEntries.map(([, d]) => Number(d?.changePct) || 0),
    ...cryptoEntries.map(([, d]) => Number(d?.changePct) || 0),
  ];
  if (allChanges.length > 2) {
    const mean = allChanges.reduce((a, b) => a + b, 0) / allChanges.length;
    const dispersion = Math.sqrt(allChanges.reduce((a, b) => a + (b - mean) ** 2, 0) / allChanges.length);
    features.push(Math.min(1, dispersion / 10));
  } else {
    features.push(0);
  }

  // Sanitize: replace NaN/Infinity with 0
  for (let i = 0; i < features.length; i++) {
    if (!Number.isFinite(features[i])) {
      features[i] = 0;
    }
  }

  return features;
}

/**
 * Build a labeled training dataset from price history buffer.
 * Label: 1 if price went up in next period, 0 if down.
 */
export function buildTrainingData(buffer, symbols, marketData) {
  const dataset = [];
  const crossFeatures = extractCrossMarketFeatures(marketData);

  for (const sym of symbols) {
    const prices = buffer.get(`${sym}_price`);
    const volumes = buffer.get(`${sym}_volume`);

    if (prices.length < 25) continue;

    // Create multiple training samples from the history using sliding windows
    for (let end = 24; end < prices.length - 1; end++) {
      const windowPrices = prices.slice(Math.max(0, end - 50), end + 1);
      const windowVolumes = volumes.slice(Math.max(0, end - 50), end + 1);
      const assetFeatures = extractAssetFeatures(windowPrices, windowVolumes);

      // Target: did price go up in next period?
      const futureReturn = (prices[end + 1] - prices[end]) / (prices[end] || 1);

      // For direction prediction (classification)
      const directionTarget = futureReturn > 0 ? 1 : 0;

      // For magnitude prediction (regression)
      const magnitudeTarget = Math.max(-1, Math.min(1, futureReturn * 100));

      dataset.push({
        input: [...assetFeatures, ...crossFeatures],
        target: [directionTarget],
        magnitude: magnitudeTarget,
        symbol: sym,
      });
    }
  }

  return dataset;
}

/**
 * Split data into train/test sets
 */
export function trainTestSplit(data, testRatio = 0.2) {
  const shuffled = fisherYatesShuffle([...data]);
  const split = Math.floor(data.length * (1 - testRatio));
  return {
    train: shuffled.slice(0, split),
    test: shuffled.slice(split),
  };
}

/**
 * Compute a composite market score from features (0-100).
 * Uses weighted combination of key indicators.
 */
export function computeMarketScore(assetFeatures, crossFeatures) {
  const weights = {
    rsi: 0.15,
    macd: 0.1,
    bollinger: 0.1,
    momentum5: 0.15,
    momentum20: 0.1,
    volume: 0.05,
    volatility: -0.1,
    maCross: 0.1,
    priceVsMa: 0.05,
    trend: 0.1,
  };

  let score = 50; // neutral baseline
  score += (assetFeatures[0] - 0.5) * 100 * weights.rsi;
  score += assetFeatures[1] * 50 * weights.macd;
  score += (assetFeatures[2] - 0.5) * 100 * weights.bollinger;
  score += assetFeatures[3] * 50 * weights.momentum5;
  score += assetFeatures[4] * 50 * weights.momentum20;
  score += (assetFeatures[5] - 1) * 30 * weights.volume;
  score += assetFeatures[6] * 100 * weights.volatility;
  score += assetFeatures[7] * 50 * weights.maCross;
  score += assetFeatures[8] * 50 * weights.priceVsMa;
  score += assetFeatures[11] * 50 * weights.trend;

  // Cross-market adjustments
  score += (crossFeatures[1] - 0.5) * 10; // market breadth
  score += crossFeatures[5] * 5; // risk on/off

  return Math.max(0, Math.min(100, score));
}
