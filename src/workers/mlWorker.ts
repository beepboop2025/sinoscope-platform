/**
 * Web Worker for ML model training and inference.
 * Moves all heavy ML computation off the main thread to prevent UI freezing.
 *
 * Message protocol:
 *   Main -> Worker: { type, payload, id }
 *   Worker -> Main: { type, payload, id, error? }
 */

import { NeuralNet, fisherYatesShuffle } from '../ml/NeuralNet';

// ── Types ────────────────────────────────────────────────────────────────────

interface TrainingDataPoint {
  input: number[];
  target: number[];
  symbol?: string;
  magnitude?: number;
}

interface TrainTestResult {
  train: TrainingDataPoint[];
  test: TrainingDataPoint[];
}

interface WorkerMessage {
  type: 'train' | 'predict' | 'detectAnomalies' | 'classifyRegime' | 'init' | 'reset';
  payload: unknown;
  id: string;
}

interface TrainPayload {
  dataset: TrainingDataPoint[];
  epochs: number;
  model: 'price' | 'regime';
  netConfig?: { layers: number[]; activation?: string; outputActivation?: string; learningRate?: number };
  serializedNet?: string;
}

interface PredictPayload {
  inputs: { symbol: string; features: number[] }[];
  serializedNet: string;
}

interface AnomalyPayload {
  symbols: { symbol: string; changePct: number; history: number[] }[];
  threshold: number;
}

interface RegimePayload {
  features: number[];
  serializedNet: string;
}

// ── Worker state ─────────────────────────────────────────────────────────────

let priceNet: NeuralNet | null = null;
let regimeNet: NeuralNet | null = null;

// ── Helpers ──────────────────────────────────────────────────────────────────

function trainTestSplit(data: TrainingDataPoint[], testRatio: number): TrainTestResult {
  const shuffled = fisherYatesShuffle([...data]);
  const testSize = Math.max(1, Math.floor(shuffled.length * testRatio));
  return {
    test: shuffled.slice(0, testSize),
    train: shuffled.slice(testSize),
  };
}

function zScore(value: number, data: number[]): number {
  const n = data.length;
  if (n < 2) return 0;
  const mean = data.reduce((a, b) => a + b, 0) / n;
  const std = Math.sqrt(data.reduce((a, b) => a + (b - mean) ** 2, 0) / n);
  return std > 0 ? (value - mean) / std : 0;
}

// ── Message handlers ─────────────────────────────────────────────────────────

function handleTrain(payload: TrainPayload): Record<string, unknown> {
  const { dataset, epochs, model, netConfig, serializedNet } = payload;

  // Restore or create the net
  let net: NeuralNet;
  if (serializedNet) {
    net = NeuralNet.deserialize(serializedNet);
  } else if (netConfig) {
    net = new NeuralNet(netConfig.layers, {
      activation: netConfig.activation,
      outputActivation: netConfig.outputActivation,
      learningRate: netConfig.learningRate,
    });
  } else {
    throw new Error('Either serializedNet or netConfig required');
  }

  // Clean dataset — filter NaN
  const clean = dataset.filter(d =>
    d.input.every(v => Number.isFinite(v)) && d.target.every(v => Number.isFinite(v))
  );
  if (clean.length < 10) {
    return { error: 'Not enough clean samples', serializedNet: net.serialize() };
  }

  const { train, test } = trainTestSplit(clean, 0.2);

  // Train
  const losses = net.train(train, epochs);

  // Evaluate
  const accuracy = test.length > 0 ? net.accuracy(test) : 0;
  let tp = 0, fp = 0, fn = 0;
  for (const { input, target } of test) {
    const pred = net.predict(input);
    const predClass = pred[0] >= 0.5 ? 1 : 0;
    const trueClass = target[0] >= 0.5 ? 1 : 0;
    if (predClass === 1 && trueClass === 1) tp++;
    else if (predClass === 1 && trueClass === 0) fp++;
    else if (predClass === 0 && trueClass === 1) fn++;
  }
  const precision = (tp + fp) > 0 ? tp / (tp + fp) : 0;
  const recall = (tp + fn) > 0 ? tp / (tp + fn) : 0;
  const f1 = (precision + recall) > 0 ? 2 * precision * recall / (precision + recall) : 0;

  // Store in worker state
  if (model === 'price') priceNet = net;
  else if (model === 'regime') regimeNet = net;

  return {
    serializedNet: net.serialize(),
    losses,
    accuracy,
    precision,
    recall,
    f1,
    trainSize: train.length,
    testSize: test.length,
    finalLoss: losses[losses.length - 1] ?? 1,
  };
}

function handlePredict(payload: PredictPayload): Record<string, unknown> {
  const { inputs, serializedNet } = payload;
  const net = NeuralNet.deserialize(serializedNet);

  const predictions: Record<string, { output: number[]; direction: string; confidence: number }> = {};
  for (const { symbol, features } of inputs) {
    if (features.some(v => !Number.isFinite(v))) continue;
    const output = net.predict(features);
    predictions[symbol] = {
      output,
      direction: output[0] >= 0.5 ? 'up' : 'down',
      confidence: Math.abs(output[0] - 0.5) * 2,
    };
  }
  return { predictions };
}

function handleDetectAnomalies(payload: AnomalyPayload): Record<string, unknown> {
  const { symbols, threshold } = payload;
  const anomalies: { symbol: string; changePct: number; zScore: number; severity: string; direction: string; timestamp: number }[] = [];

  for (const { symbol, changePct, history } of symbols) {
    if (history.length < 5) continue;
    const z = zScore(changePct, history);
    if (Math.abs(z) >= threshold) {
      const absZ = Math.abs(z);
      anomalies.push({
        symbol,
        changePct,
        zScore: z,
        severity: absZ >= 3 ? 'critical' : absZ >= 2.5 ? 'high' : absZ >= 2 ? 'medium' : 'low',
        direction: z > 0 ? 'up' : 'down',
        timestamp: Date.now(),
      });
    }
  }

  return { anomalies };
}

function handleClassifyRegime(payload: RegimePayload): Record<string, unknown> {
  const { features, serializedNet } = payload;
  const net = NeuralNet.deserialize(serializedNet);
  const output = net.predict(features);

  // Interpret output: 3-class classification [bull, bear, sideways]
  const labels = ['bull', 'bear', 'sideways'];
  const maxIdx = output.indexOf(Math.max(...output));
  return {
    regime: labels[maxIdx] || 'unknown',
    confidence: output[maxIdx] || 0,
    probabilities: { bull: output[0], bear: output[1], sideways: output[2] },
  };
}

// ── Main message listener ────────────────────────────────────────────────────

self.addEventListener('message', (e: MessageEvent<WorkerMessage>) => {
  const { type, payload, id } = e.data;

  try {
    let result: Record<string, unknown>;

    switch (type) {
      case 'train':
        result = handleTrain(payload as TrainPayload);
        break;
      case 'predict':
        result = handlePredict(payload as PredictPayload);
        break;
      case 'detectAnomalies':
        result = handleDetectAnomalies(payload as AnomalyPayload);
        break;
      case 'classifyRegime':
        result = handleClassifyRegime(payload as RegimePayload);
        break;
      case 'reset':
        priceNet = null;
        regimeNet = null;
        result = { ok: true };
        break;
      default:
        result = { error: `Unknown message type: ${type}` };
    }

    self.postMessage({ type, payload: result, id });
  } catch (err) {
    self.postMessage({
      type,
      id,
      error: err instanceof Error ? err.message : String(err),
    });
  }
});

// Signal readiness
self.postMessage({ type: 'ready', payload: {}, id: '__init__' });
