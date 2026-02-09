/**
 * MLEngine — central orchestrator for all ML models.
 * Manages data buffering, training loops, and prediction generation.
 */

import { RollingBuffer, extractAssetFeatures, extractCrossMarketFeatures, buildTrainingData, trainTestSplit } from './FeatureEngine';
import { PricePredictor, AnomalyDetector, MarketRegime, SignalGenerator } from './Models';
import type { MarketSnapshot, MarketTick } from '../types/market';
import type { TrainingDataPoint } from '../types/ml';

const TRAIN_INTERVAL = 60_000; // retrain every 60s
const MIN_DATA_POINTS = 30;    // minimum history before training
const PREDICT_INTERVAL = 5_000; // generate predictions every 5s

interface TrainingStatus {
  isTraining: boolean;
  lastTrained: number | null;
  epochs: number;
  dataPoints: number;
  priceAccuracy: number;
  regimeAccuracy: number;
  priceLoss: number;
  trainSize?: number;
  testSize?: number;
  precision?: number;
  recall?: number;
  f1?: number;
}

interface MLEngineState {
  trainingStatus: TrainingStatus;
  predictions: Record<string, unknown>;
  signals: unknown[];
  signalSummary: unknown;
  anomalies: unknown[];
  anomalyStats: unknown;
  trackedSymbols: number;
  dataPoints: number;
  trainLoss: number[];
}

type MLStateListener = (state: MLEngineState) => void;

export class MLEngine {
  buffer: RollingBuffer;
  pricePredictor: PricePredictor;
  anomalyDetector: AnomalyDetector;
  marketRegime: MarketRegime;
  signalGenerator: SignalGenerator;
  lastTrainTime: number;
  lastPredictTime: number;
  trackedSymbols: Set<string>;
  latestMarketData: MarketSnapshot | null;
  trainingStatus: TrainingStatus;
  predictions: Record<string, unknown>;
  listeners: Set<MLStateListener>;

  constructor() {
    this.buffer = new RollingBuffer(200);
    this.pricePredictor = new PricePredictor();
    this.anomalyDetector = new AnomalyDetector();
    this.marketRegime = new MarketRegime();
    this.signalGenerator = new SignalGenerator(
      this.pricePredictor,
      this.anomalyDetector,
      this.marketRegime
    );

    this.lastTrainTime = 0;
    this.lastPredictTime = 0;
    this.trackedSymbols = new Set();
    this.latestMarketData = null;
    this.trainingStatus = {
      isTraining: false,
      lastTrained: null,
      epochs: 0,
      dataPoints: 0,
      priceAccuracy: 0,
      regimeAccuracy: 0,
      priceLoss: 1,
    };
    this.predictions = {};
    this.listeners = new Set();

    // Try loading saved models
    this.pricePredictor.load();
    this.marketRegime.load();
    this.anomalyDetector.load();

    // Validate loaded models with a test forward pass
    this._validateLoadedModels();
  }

  _validateLoadedModels(): void {
    const dummyInput: number[] = new Array(20).fill(0);
    try {
      if (this.pricePredictor.trained) {
        const out = this.pricePredictor.net.predict(dummyInput);
        if (!out.every(v => Number.isFinite(v))) {
          console.warn('MLEngine: PricePredictor loaded weights are corrupted, reinitializing');
          this.pricePredictor = new PricePredictor();
        }
      }
    } catch (err: unknown) {
      console.warn('MLEngine: PricePredictor validation failed, reinitializing:', err);
      this.pricePredictor = new PricePredictor();
    }
    try {
      if (this.marketRegime.trained) {
        const out = this.marketRegime.net.predict(dummyInput);
        if (!out.every(v => Number.isFinite(v))) {
          console.warn('MLEngine: MarketRegime loaded weights are corrupted, reinitializing');
          this.marketRegime = new MarketRegime();
        }
      }
    } catch (err: unknown) {
      console.warn('MLEngine: MarketRegime validation failed, reinitializing:', err);
      this.marketRegime = new MarketRegime();
    }
  }

  // Subscribe to updates
  subscribe(fn: MLStateListener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  notify(): void {
    const state = this.getState();
    for (const fn of this.listeners) {
      try { fn(state); } catch { /* ignore */ }
    }
  }

  // Ingest new market data snapshot
  ingest(marketData: MarketSnapshot | null): void {
    if (!marketData) return;
    this.latestMarketData = marketData;

    // Buffer price and volume data for each asset
    const now = Date.now();

    // Stocks
    for (const [sym, d] of Object.entries(marketData.stocks || {}) as [string, MarketTick][]) {
      const price = Number(d?.price) || 0;
      if (price > 0) {
        this.buffer.push(`${sym}_price`, price);
        this.buffer.push(`${sym}_volume`, Number(d?.volume) || 0);
        this.trackedSymbols.add(sym);
      }
    }

    // Crypto
    for (const [sym, d] of Object.entries(marketData.crypto || {}) as [string, MarketTick][]) {
      const price = Number(d?.price) || 0;
      if (price > 0) {
        this.buffer.push(`${sym}_price`, price);
        this.buffer.push(`${sym}_volume`, Number(d?.volume) || 0);
        this.trackedSymbols.add(sym);
      }
    }

    // Auto-train if enough data and interval elapsed
    if (now - this.lastTrainTime > TRAIN_INTERVAL && this.getDataSize() >= MIN_DATA_POINTS) {
      this.train();
    }

    // Auto-predict
    if (now - this.lastPredictTime > PREDICT_INTERVAL) {
      this.predictAll();
    }
  }

  getDataSize(): number {
    let total = 0;
    for (const sym of this.trackedSymbols) {
      total += this.buffer.len(`${sym}_price`);
    }
    return total;
  }

  // Train all models
  train(): void {
    if (this.trainingStatus.isTraining) return;

    const symbols = [...this.trackedSymbols];
    if (symbols.length === 0) return;

    this.trainingStatus.isTraining = true;
    this.notify();

    try {
      // Build training dataset
      const dataset = buildTrainingData(this.buffer, symbols, this.latestMarketData);
      if (dataset.length < 10) {
        this.trainingStatus.isTraining = false;
        this.notify();
        return;
      }

      // Validate feature vectors: check for NaN values
      const cleanDataset = dataset.filter(d => {
        const hasNaN = d.input.some(v => !Number.isFinite(v));
        if (hasNaN) console.warn('MLEngine: dropping sample with NaN/Infinity in features for', d.symbol);
        return !hasNaN;
      });

      if (cleanDataset.length < 10) {
        console.warn('MLEngine: not enough clean samples after NaN filtering');
        this.trainingStatus.isTraining = false;
        this.notify();
        return;
      }

      const { train, test } = trainTestSplit(cleanDataset, 0.2);

      // Validate train/test split produced non-empty arrays
      if (train.length === 0 || test.length === 0) {
        console.warn('MLEngine: train/test split produced empty set, using full dataset for both');
        train.length === 0 && train.push(...cleanDataset);
        test.length === 0 && test.push(...cleanDataset.slice(-Math.max(1, Math.floor(cleanDataset.length * 0.2))));
      }

      // Check for class imbalance
      const positiveCount = train.filter(d => d.target[0] >= 0.5).length;
      const positiveRatio = positiveCount / train.length;
      if (positiveRatio > 0.8 || positiveRatio < 0.2) {
        console.warn(`MLEngine: class imbalance detected — ${(positiveRatio * 100).toFixed(1)}% positive samples`);
      }

      // Train price predictor
      const priceMetrics = this.pricePredictor.train(train, 20);

      // Train regime classifier
      const regimeMetrics = this.marketRegime.train(train, 20);

      // Evaluate on test set
      const testAccuracy = test.length > 0 ? this.pricePredictor.net.accuracy(test) : priceMetrics.accuracy;

      // Compute precision, recall, F1 on test set
      let tp = 0, fp = 0, fn = 0, tn = 0;
      for (const { input, target } of test) {
        const pred = this.pricePredictor.net.predict(input);
        const predClass = pred[0] >= 0.5 ? 1 : 0;
        const trueClass = target[0] >= 0.5 ? 1 : 0;
        if (predClass === 1 && trueClass === 1) tp++;
        else if (predClass === 1 && trueClass === 0) fp++;
        else if (predClass === 0 && trueClass === 1) fn++;
        else tn++;
      }
      const precision = (tp + fp) > 0 ? tp / (tp + fp) : 0;
      const recall = (tp + fn) > 0 ? tp / (tp + fn) : 0;
      const f1 = (precision + recall) > 0 ? 2 * precision * recall / (precision + recall) : 0;

      this.trainingStatus = {
        isTraining: false,
        lastTrained: Date.now(),
        epochs: this.trainingStatus.epochs + 20,
        dataPoints: cleanDataset.length,
        priceAccuracy: testAccuracy,
        regimeAccuracy: regimeMetrics.accuracy,
        priceLoss: priceMetrics.loss,
        trainSize: train.length,
        testSize: test.length,
        precision,
        recall,
        f1,
      };

      this.lastTrainTime = Date.now();
    } catch (err: unknown) {
      console.warn('ML training error:', err);
      this.trainingStatus.isTraining = false;
    }

    this.notify();
  }

  // Generate predictions for all tracked symbols
  predictAll(): void {
    if (!this.latestMarketData) return;

    const crossFeatures = extractCrossMarketFeatures(this.latestMarketData);

    for (const sym of this.trackedSymbols) {
      const prices = this.buffer.get(`${sym}_price`);
      const volumes = this.buffer.get(`${sym}_volume`);
      if (prices.length < 5) continue;

      const assetFeatures = extractAssetFeatures(prices, volumes);
      const changePct = prices.length >= 2
        ? ((prices[prices.length - 1] - prices[prices.length - 2]) / (prices[prices.length - 2] || 1)) * 100
        : 0;

      const signal = this.signalGenerator.generate(sym, assetFeatures, crossFeatures, changePct);
      this.predictions[sym] = signal;
    }

    this.lastPredictTime = Date.now();
    this.notify();
  }

  // Get current state for UI
  getState(): MLEngineState {
    return {
      trainingStatus: { ...this.trainingStatus },
      predictions: { ...this.predictions },
      signals: this.signalGenerator.getSignals(),
      signalSummary: this.signalGenerator.getSummary(),
      anomalies: this.anomalyDetector.getRecentAnomalies(),
      anomalyStats: this.anomalyDetector.getStats(),
      trackedSymbols: this.trackedSymbols.size,
      dataPoints: this.getDataSize(),
      trainLoss: this.pricePredictor.net.trainLoss.slice(-50),
    };
  }

  // Force retrain
  forceRetrain(): void {
    this.lastTrainTime = 0;
    this.train();
  }

  // Reset all models
  reset(): void {
    this.buffer.clear();
    this.trackedSymbols.clear();
    this.predictions = {};
    this.pricePredictor = new PricePredictor();
    this.anomalyDetector = new AnomalyDetector();
    this.marketRegime = new MarketRegime();
    this.signalGenerator = new SignalGenerator(
      this.pricePredictor,
      this.anomalyDetector,
      this.marketRegime
    );
    this.trainingStatus = {
      isTraining: false,
      lastTrained: null,
      epochs: 0,
      dataPoints: 0,
      priceAccuracy: 0,
      regimeAccuracy: 0,
      priceLoss: 1,
    };
    try {
      window.localStorage.removeItem('dragonscope_ml_price_predictor');
      window.localStorage.removeItem('dragonscope_ml_regime');
      window.localStorage.removeItem('dragonscope_ml_anomaly_detector');
    } catch { /* storage unavailable */ }
    this.notify();
  }
}
