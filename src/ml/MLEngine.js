/**
 * MLEngine — central orchestrator for all ML models.
 * Manages data buffering, training loops, and prediction generation.
 */

import { RollingBuffer, extractAssetFeatures, extractCrossMarketFeatures, buildTrainingData, trainTestSplit } from './FeatureEngine.js';
import { PricePredictor, AnomalyDetector, MarketRegime, SignalGenerator } from './Models.js';

const TRAIN_INTERVAL = 60_000; // retrain every 60s
const MIN_DATA_POINTS = 30;    // minimum history before training
const PREDICT_INTERVAL = 5_000; // generate predictions every 5s

export class MLEngine {
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
  }

  // Subscribe to updates
  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  notify() {
    const state = this.getState();
    for (const fn of this.listeners) {
      try { fn(state); } catch { /* ignore */ }
    }
  }

  // Ingest new market data snapshot
  ingest(marketData) {
    if (!marketData) return;
    this.latestMarketData = marketData;

    // Buffer price and volume data for each asset
    const now = Date.now();

    // Stocks
    for (const [sym, d] of Object.entries(marketData.stocks || {})) {
      const price = Number(d?.price) || 0;
      if (price > 0) {
        this.buffer.push(`${sym}_price`, price);
        this.buffer.push(`${sym}_volume`, Number(d?.volume) || 0);
        this.trackedSymbols.add(sym);
      }
    }

    // Crypto
    for (const [sym, d] of Object.entries(marketData.crypto || {})) {
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

  getDataSize() {
    let total = 0;
    for (const sym of this.trackedSymbols) {
      total += this.buffer.len(`${sym}_price`);
    }
    return total;
  }

  // Train all models
  train() {
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

      const { train, test } = trainTestSplit(dataset, 0.2);

      // Train price predictor
      const priceMetrics = this.pricePredictor.train(train, 20);

      // Train regime classifier
      const regimeMetrics = this.marketRegime.train(train, 20);

      // Evaluate on test set
      const testAccuracy = test.length > 0 ? this.pricePredictor.net.accuracy(test) : priceMetrics.accuracy;

      this.trainingStatus = {
        isTraining: false,
        lastTrained: Date.now(),
        epochs: this.trainingStatus.epochs + 20,
        dataPoints: dataset.length,
        priceAccuracy: testAccuracy,
        regimeAccuracy: regimeMetrics.accuracy,
        priceLoss: priceMetrics.loss,
        trainSize: train.length,
        testSize: test.length,
      };

      this.lastTrainTime = Date.now();
    } catch (err) {
      console.warn('ML training error:', err);
      this.trainingStatus.isTraining = false;
    }

    this.notify();
  }

  // Generate predictions for all tracked symbols
  predictAll() {
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
  getState() {
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
  forceRetrain() {
    this.lastTrainTime = 0;
    this.train();
  }

  // Reset all models
  reset() {
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
      localStorage.removeItem('dragonscope_ml_price_predictor');
      localStorage.removeItem('dragonscope_ml_regime');
    } catch { /* ignore */ }
    this.notify();
  }
}
