/**
 * ML Models for financial market analysis.
 * - PricePredictor: direction classification (up/down)
 * - AnomalyDetector: z-score based anomaly detection
 * - MarketRegime: bull/bear/sideways classifier
 * - SignalGenerator: composite buy/sell/hold signals
 */

import { NeuralNet, LinearRegression, zScore } from './NeuralNet';
import { extractAssetFeatures, extractCrossMarketFeatures, computeMarketScore } from './FeatureEngine';
import { storageWrite, storageRead } from '../utils/storage';
import type { TrainingDataPoint } from '../types/ml';

const STORAGE_PREFIX = 'dragonscope_ml_';

interface PricePredictorMetrics {
  accuracy: number;
  loss: number;
  epochs: number;
  samples: number;
}

interface PricePrediction {
  direction: string;
  confidence: number;
  probability?: number;
}

interface DetectedAnomaly {
  symbol: string;
  changePct: number;
  zScore: number;
  severity: string;
  direction: string;
  timestamp: number;
}

interface AnomalyDetectorSavedData {
  history: Record<string, number[]>;
  threshold: number;
  anomalies: DetectedAnomaly[];
}

interface AnomalyStats {
  trackedSymbols: number;
  totalAnomalies: number;
  threshold: number;
}

interface RegimeMetrics {
  accuracy: number;
  epochs: number;
}

interface RegimeHistoryEntry {
  regime: string;
  timestamp: number;
}

interface RegimePrediction {
  regime: string;
  confidence: number;
  probabilities?: { bear: number; sideways: number; bull: number };
}

interface TrainingDataPointWithMagnitude extends TrainingDataPoint {
  magnitude: number;
}

interface GeneratedSignal {
  symbol: string;
  action: string;
  strength: string;
  score: number;
  techScore: number;
  pricePrediction: PricePrediction;
  regime: string;
  regimeConfidence: number;
  anomaly: string | null;
  timestamp: number;
}

interface SignalSummary {
  total: number;
  buys: number;
  sells: number;
  holds: number;
  avgScore: number;
  strongBuys: string[];
  strongSells: string[];
}

/**
 * Predicts price direction (up/down) using a neural network.
 */
export class PricePredictor {
  net: NeuralNet;
  trained: boolean;
  metrics: PricePredictorMetrics;

  constructor() {
    // 12 asset features + 8 cross-market features = 20 inputs
    this.net = new NeuralNet([20, 32, 16, 1], {
      activation: 'relu',
      outputActivation: 'sigmoid',
      learningRate: 0.005,
      l2Lambda: 0.0001,
    });
    this.trained = false;
    this.metrics = { accuracy: 0, loss: 1, epochs: 0, samples: 0 };
  }

  train(dataset: TrainingDataPoint[], epochs: number = 30): PricePredictorMetrics {
    if (dataset.length < 10) return this.metrics;

    const losses = this.net.train(dataset, epochs);
    this.trained = true;
    this.metrics.loss = losses[losses.length - 1];
    this.metrics.epochs += epochs;
    this.metrics.samples = dataset.length;
    this.metrics.accuracy = this.net.accuracy(dataset);
    this.save();
    return this.metrics;
  }

  predict(assetFeatures: number[], crossFeatures: number[]): PricePrediction {
    if (!this.trained) return { direction: 'neutral', confidence: 0.5 };
    const input = [...assetFeatures, ...crossFeatures];
    const [prob] = this.net.predict(input);
    const direction = prob > 0.6 ? 'up' : prob < 0.4 ? 'down' : 'neutral';
    const confidence = Math.abs(prob - 0.5) * 2;
    return { direction, confidence, probability: prob };
  }

  save(): void {
    storageWrite(STORAGE_PREFIX + 'price_predictor', this.net.serialize());
  }

  load(): boolean {
    try {
      const json = storageRead<string>(STORAGE_PREFIX + 'price_predictor');
      if (json) {
        this.net = NeuralNet.deserialize(json);
        this.trained = true;
        return true;
      }
    } catch (err: unknown) {
      console.warn('[PricePredictor] load failed:', (err as Error).message);
    }
    return false;
  }
}

/**
 * Detects anomalous price movements using z-scores and a learned threshold.
 */
export class AnomalyDetector {
  history: Record<string, number[]>;
  maxHistory: number;
  threshold: number;
  anomalies: DetectedAnomaly[];
  maxAnomalies: number;

  constructor() {
    this.history = {}; // symbol -> recent changes[]
    this.maxHistory = 200;
    this.threshold = 2.5; // z-score threshold
    this.anomalies = []; // recent anomalies for display
    this.maxAnomalies = 50;
  }

  update(symbol: string, changePct: number): void {
    if (!this.history[symbol]) this.history[symbol] = [];
    this.history[symbol].push(changePct);
    if (this.history[symbol].length > this.maxHistory) {
      this.history[symbol].shift();
    }
  }

  detect(symbol: string, changePct: number): DetectedAnomaly | null {
    const hist = this.history[symbol] || [];
    if (hist.length < 10) return null;

    const z = zScore(changePct, hist);
    const isAnomaly = Math.abs(z) > this.threshold;

    if (isAnomaly) {
      const anomaly: DetectedAnomaly = {
        symbol,
        changePct,
        zScore: z,
        severity: Math.abs(z) > 4 ? 'critical' : Math.abs(z) > 3 ? 'high' : 'medium',
        direction: changePct > 0 ? 'spike' : 'crash',
        timestamp: Date.now(),
      };
      this.anomalies.unshift(anomaly);
      if (this.anomalies.length > this.maxAnomalies) this.anomalies.pop();
      this.save();
      return anomaly;
    }
    return null;
  }

  save(): void {
    storageWrite(STORAGE_PREFIX + 'anomaly_detector', {
      history: this.history,
      threshold: this.threshold,
      anomalies: this.anomalies.slice(0, 20),
    });
  }

  load(): boolean {
    try {
      const data = storageRead<AnomalyDetectorSavedData>(STORAGE_PREFIX + 'anomaly_detector');
      if (data) {
        this.history = data.history || {};
        this.threshold = data.threshold || 2.5;
        this.anomalies = data.anomalies || [];
        return true;
      }
    } catch (err: unknown) {
      console.warn('[AnomalyDetector] load failed:', (err as Error).message);
    }
    return false;
  }

  getRecentAnomalies(limit: number = 10): DetectedAnomaly[] {
    return this.anomalies.slice(0, limit);
  }

  getStats(): AnomalyStats {
    return {
      trackedSymbols: Object.keys(this.history).length,
      totalAnomalies: this.anomalies.length,
      threshold: this.threshold,
    };
  }
}

/**
 * Classifies market regime as bull, bear, or sideways.
 * Uses a neural network with 3-class output.
 */
export class MarketRegime {
  net: NeuralNet;
  trained: boolean;
  regimeLabels: string[];
  metrics: RegimeMetrics;
  currentRegime: string;
  regimeHistory: RegimeHistoryEntry[];

  constructor() {
    this.net = new NeuralNet([20, 24, 12, 3], {
      activation: 'relu',
      outputActivation: 'sigmoid',
      learningRate: 0.005,
      l2Lambda: 0.0001,
    });
    this.trained = false;
    this.regimeLabels = ['bear', 'sideways', 'bull'];
    this.metrics = { accuracy: 0, epochs: 0 };
    this.currentRegime = 'sideways';
    this.regimeHistory = [];
  }

  // Generate training labels from price data
  static labelRegime(prices: number[], lookback: number = 20): number[] {
    if (prices.length < lookback) return [0, 1, 0]; // sideways default
    const returns = (prices[prices.length - 1] - prices[prices.length - lookback]) / (prices[prices.length - lookback] || 1);
    if (returns > 0.05) return [0, 0, 1];    // bull: >5% gain
    if (returns < -0.05) return [1, 0, 0];   // bear: >5% loss
    return [0, 1, 0];                         // sideways
  }

  train(dataset: TrainingDataPointWithMagnitude[], epochs: number = 30): RegimeMetrics {
    if (dataset.length < 10) return this.metrics;
    // Convert direction targets to regime targets
    const regimeData: TrainingDataPoint[] = dataset.map(d => ({
      input: d.input,
      target: d.magnitude > 0.3 ? [0, 0, 1] : d.magnitude < -0.3 ? [1, 0, 0] : [0, 1, 0],
    }));
    this.net.train(regimeData, epochs);
    this.trained = true;
    this.metrics.accuracy = this.net.accuracy(regimeData);
    this.metrics.epochs += epochs;
    this.save();
    return this.metrics;
  }

  predict(assetFeatures: number[], crossFeatures: number[]): RegimePrediction {
    if (!this.trained) {
      // Fallback: use simple momentum-based regime detection
      const momentum = assetFeatures[3]; // 5-period momentum
      const trend = assetFeatures[11]; // trend strength
      if (momentum > 0.2 && trend > 0.2) return { regime: 'bull', confidence: 0.6 };
      if (momentum < -0.2 && trend < -0.2) return { regime: 'bear', confidence: 0.6 };
      return { regime: 'sideways', confidence: 0.5 };
    }

    const input = [...assetFeatures, ...crossFeatures];
    const probs = this.net.predict(input);
    const maxIdx = probs.indexOf(Math.max(...probs));
    const regime = this.regimeLabels[maxIdx];
    const confidence = probs[maxIdx];

    this.currentRegime = regime;
    this.regimeHistory.push({ regime, timestamp: Date.now() });
    if (this.regimeHistory.length > 100) this.regimeHistory.shift();

    return { regime, confidence, probabilities: { bear: probs[0], sideways: probs[1], bull: probs[2] } };
  }

  save(): void {
    storageWrite(STORAGE_PREFIX + 'regime', this.net.serialize());
  }

  load(): boolean {
    try {
      const json = storageRead<string>(STORAGE_PREFIX + 'regime');
      if (json) {
        this.net = NeuralNet.deserialize(json);
        this.trained = true;
        return true;
      }
    } catch (err: unknown) {
      console.warn('[MarketRegime] load failed:', (err as Error).message);
    }
    return false;
  }
}

/**
 * Generates composite trading signals by combining all models.
 */
export class SignalGenerator {
  pricePredictor: PricePredictor;
  anomalyDetector: AnomalyDetector;
  marketRegime: MarketRegime;
  signals: Record<string, GeneratedSignal>;

  constructor(pricePredictor: PricePredictor, anomalyDetector: AnomalyDetector, marketRegime: MarketRegime) {
    this.pricePredictor = pricePredictor;
    this.anomalyDetector = anomalyDetector;
    this.marketRegime = marketRegime;
    this.signals = {}; // symbol -> latest signal
  }

  generate(symbol: string, assetFeatures: number[], crossFeatures: number[], changePct: number): GeneratedSignal {
    // 1. Price direction prediction
    const pricePred = this.pricePredictor.predict(assetFeatures, crossFeatures);

    // 2. Anomaly check
    this.anomalyDetector.update(symbol, changePct);
    const anomaly = this.anomalyDetector.detect(symbol, changePct);

    // 3. Market regime
    const regime = this.marketRegime.predict(assetFeatures, crossFeatures);

    // 4. Technical score
    const techScore = computeMarketScore(assetFeatures, crossFeatures);

    // 5. Composite signal
    let signalScore = 0;

    // Price prediction contribution (40%)
    if (pricePred.direction === 'up') signalScore += 40 * pricePred.confidence;
    else if (pricePred.direction === 'down') signalScore -= 40 * pricePred.confidence;

    // Regime contribution (25%)
    if (regime.regime === 'bull') signalScore += 25 * regime.confidence;
    else if (regime.regime === 'bear') signalScore -= 25 * regime.confidence;

    // Technical score contribution (25%)
    signalScore += (techScore - 50) * 0.5;

    // Anomaly override (10%) — anomalies increase caution
    if (anomaly) {
      signalScore *= 0.5; // dampen signal during anomalies
    }

    // Normalize to -100 to 100
    signalScore = Math.max(-100, Math.min(100, signalScore));

    // Generate action
    let action: string, strength: string;
    if (signalScore > 25) {
      action = 'buy';
      strength = signalScore > 60 ? 'strong' : 'moderate';
    } else if (signalScore < -25) {
      action = 'sell';
      strength = signalScore < -60 ? 'strong' : 'moderate';
    } else {
      action = 'hold';
      strength = 'neutral';
    }

    const signal: GeneratedSignal = {
      symbol,
      action,
      strength,
      score: signalScore,
      techScore,
      pricePrediction: pricePred,
      regime: regime.regime,
      regimeConfidence: regime.confidence,
      anomaly: anomaly ? anomaly.severity : null,
      timestamp: Date.now(),
    };

    this.signals[symbol] = signal;
    return signal;
  }

  getSignals(): GeneratedSignal[] {
    return Object.values(this.signals).sort((a, b) => Math.abs(b.score) - Math.abs(a.score));
  }

  getSignal(symbol: string): GeneratedSignal | null {
    return this.signals[symbol] || null;
  }

  getSummary(): SignalSummary {
    const signals = this.getSignals();
    const buys = signals.filter(s => s.action === 'buy');
    const sells = signals.filter(s => s.action === 'sell');
    const holds = signals.filter(s => s.action === 'hold');
    const avgScore = signals.length > 0
      ? signals.reduce((s, sig) => s + sig.score, 0) / signals.length
      : 0;

    return {
      total: signals.length,
      buys: buys.length,
      sells: sells.length,
      holds: holds.length,
      avgScore: Math.round(avgScore),
      strongBuys: buys.filter(s => s.strength === 'strong').map(s => s.symbol),
      strongSells: sells.filter(s => s.strength === 'strong').map(s => s.symbol),
    };
  }
}
