/**
 * Lightweight feedforward neural network with backpropagation.
 * Runs entirely in the browser — no dependencies.
 */

import type { TrainingDataPoint } from '../types/ml';

// Activation functions
interface ActivationPair {
  fn: (x: number) => number;
  deriv: (x: number) => number;
}

interface ForwardResult {
  output: number[];
  activations: number[][];
  zs: number[][];
}

interface NeuralNetOptions {
  activation?: string;
  outputActivation?: string;
  learningRate?: number;
  l2Lambda?: number;
}

interface SerializedNet {
  layers: number[];
  weights: number[][][];
  biases: number[][];
  activation: string;
  outputActivation: string;
  lr: number;
}

const activations: Record<string, ActivationPair> = {
  relu: {
    fn: (x: number): number => Math.max(0, x),
    deriv: (x: number): number => x > 0 ? 1 : 0,
  },
  sigmoid: {
    fn: (x: number): number => 1 / (1 + Math.exp(-Math.max(-500, Math.min(500, x)))),
    deriv: (x: number): number => { const s = 1 / (1 + Math.exp(-Math.max(-500, Math.min(500, x)))); return s * (1 - s); },
  },
  tanh: {
    fn: (x: number): number => Math.tanh(x),
    deriv: (x: number): number => 1 - Math.tanh(x) ** 2,
  },
  linear: {
    fn: (x: number): number => x,
    deriv: (): number => 1,
  },
};

function randn(): number {
  // Box-Muller transform
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1 || 1e-10)) * Math.cos(2 * Math.PI * u2);
}

/** Proper Fisher-Yates (Durstenfeld) shuffle — unbiased O(n) */
export function fisherYatesShuffle<T>(arr: T[]): T[] {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    const tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }
  return arr;
}

export class NeuralNet {
  layers: number[];
  activation: string;
  outputActivation: string;
  lr: number;
  l2: number;
  weights: number[][][];
  biases: number[][];
  trainLoss: number[];

  /**
   * @param layers - e.g. [10, 16, 8, 3] for 10 inputs, 2 hidden layers, 3 outputs
   * @param opts - { activation, learningRate, l2Lambda }
   */
  constructor(layers: number[], opts: NeuralNetOptions = {}) {
    this.layers = layers;
    this.activation = opts.activation || 'relu';
    this.outputActivation = opts.outputActivation || 'sigmoid';
    this.lr = opts.learningRate || 0.01;
    this.l2 = opts.l2Lambda || 0.0001;

    // Xavier initialization
    this.weights = [];
    this.biases = [];
    for (let i = 0; i < layers.length - 1; i++) {
      const fanIn = layers[i];
      const fanOut = layers[i + 1];
      const scale = Math.sqrt(2 / (fanIn + fanOut));
      const w: number[][] = [];
      for (let j = 0; j < fanOut; j++) {
        const row: number[] = [];
        for (let k = 0; k < fanIn; k++) {
          row.push(randn() * scale);
        }
        w.push(row);
      }
      this.weights.push(w);
      this.biases.push(new Array(fanOut).fill(0) as number[]);
    }

    this.trainLoss = [];
  }

  forward(input: number[]): ForwardResult {
    const acts: number[][] = [input];
    const zs: number[][] = [];
    let current = input;

    for (let l = 0; l < this.weights.length; l++) {
      const w = this.weights[l];
      const b = this.biases[l];
      const isOutput = l === this.weights.length - 1;
      const actFn = isOutput ? activations[this.outputActivation] : activations[this.activation];
      const z: number[] = [];
      const a: number[] = [];

      for (let j = 0; j < w.length; j++) {
        let sum = b[j];
        for (let k = 0; k < current.length; k++) {
          sum += w[j][k] * current[k];
        }
        z.push(sum);
        a.push(actFn.fn(sum));
      }
      zs.push(z);
      acts.push(a);
      current = a;
    }

    return { output: current, activations: acts, zs };
  }

  predict(input: number[]): number[] {
    const output = this.forward(input).output;
    // Guard against NaN/Infinity in predictions
    for (let i = 0; i < output.length; i++) {
      if (!Number.isFinite(output[i])) output[i] = 0.5;
    }
    return output;
  }

  // Backpropagation
  backward(input: number[], target: number[]): number {
    // Validate inputs
    if (input.some(v => !Number.isFinite(v)) || target.some(v => !Number.isFinite(v))) {
      return 1; // Return high loss for invalid inputs
    }

    const { output, activations: acts, zs } = this.forward(input);

    // Early exit if output contains NaN (network is corrupted)
    if (output.some(v => !Number.isFinite(v))) {
      return 1;
    }

    const numLayers = this.weights.length;
    const deltas: number[][] = new Array(numLayers);
    const outputActDeriv = activations[this.outputActivation].deriv;
    const hiddenActDeriv = activations[this.activation].deriv;

    // Output delta
    const outputDelta: number[] = [];
    for (let j = 0; j < output.length; j++) {
      outputDelta.push((output[j] - target[j]) * outputActDeriv(zs[numLayers - 1][j]));
    }
    deltas[numLayers - 1] = outputDelta;

    // Hidden layer deltas
    for (let l = numLayers - 2; l >= 0; l--) {
      const delta: number[] = [];
      for (let j = 0; j < this.weights[l].length; j++) {
        let err = 0;
        for (let k = 0; k < this.weights[l + 1].length; k++) {
          err += this.weights[l + 1][k][j] * deltas[l + 1][k];
        }
        delta.push(err * hiddenActDeriv(zs[l][j]));
      }
      deltas[l] = delta;
    }

    // Gradient clipping: cap deltas to [-5, 5]
    for (let l = 0; l < numLayers; l++) {
      for (let j = 0; j < deltas[l].length; j++) {
        if (!Number.isFinite(deltas[l][j])) {
          deltas[l][j] = 0;
        } else {
          deltas[l][j] = Math.max(-5, Math.min(5, deltas[l][j]));
        }
      }
    }

    // Update weights and biases with gradient clipping
    for (let l = 0; l < numLayers; l++) {
      const a = acts[l];
      for (let j = 0; j < this.weights[l].length; j++) {
        for (let k = 0; k < this.weights[l][j].length; k++) {
          const grad = deltas[l][j] * a[k] + this.l2 * this.weights[l][j][k];
          // Clip individual gradients
          const clippedGrad = Math.max(-10, Math.min(10, grad));
          this.weights[l][j][k] -= this.lr * clippedGrad;
          // Reset corrupted weights
          if (!Number.isFinite(this.weights[l][j][k])) {
            this.weights[l][j][k] = randn() * 0.01;
          }
        }
        this.biases[l][j] -= this.lr * deltas[l][j];
        if (!Number.isFinite(this.biases[l][j])) {
          this.biases[l][j] = 0;
        }
      }
    }

    // MSE loss
    let loss = 0;
    for (let j = 0; j < output.length; j++) {
      loss += (output[j] - target[j]) ** 2;
    }
    const avgLoss = loss / output.length;
    return Number.isFinite(avgLoss) ? avgLoss : 1;
  }

  // Train on dataset
  train(data: TrainingDataPoint[], epochs: number = 50): number[] {
    const losses: number[] = [];
    for (let e = 0; e < epochs; e++) {
      let totalLoss = 0;
      const shuffled = fisherYatesShuffle([...data]);
      for (const { input, target } of shuffled) {
        totalLoss += this.backward(input, target);
      }
      const avgLoss = totalLoss / data.length;
      losses.push(avgLoss);
      this.trainLoss.push(avgLoss);
      // Cap trainLoss history to prevent unbounded growth
      if (this.trainLoss.length > 500) {
        this.trainLoss = this.trainLoss.slice(-250);
      }
    }
    return losses;
  }

  // Get accuracy for classification
  accuracy(data: TrainingDataPoint[]): number {
    let correct = 0;
    for (const { input, target } of data) {
      const pred = this.predict(input);
      if (pred.length === 1) {
        if ((pred[0] >= 0.5 ? 1 : 0) === (target[0] >= 0.5 ? 1 : 0)) correct++;
      } else {
        const predIdx = pred.indexOf(Math.max(...pred));
        const targetIdx = target.indexOf(Math.max(...target));
        if (predIdx === targetIdx) correct++;
      }
    }
    return data.length > 0 ? correct / data.length : 0;
  }

  serialize(): string {
    return JSON.stringify({ layers: this.layers, weights: this.weights, biases: this.biases, activation: this.activation, outputActivation: this.outputActivation, lr: this.lr });
  }

  static deserialize(json: string): NeuralNet {
    const d = JSON.parse(json) as SerializedNet;
    const net = new NeuralNet(d.layers, { activation: d.activation, outputActivation: d.outputActivation, learningRate: d.lr });
    net.weights = d.weights;
    net.biases = d.biases;
    return net;
  }
}

// Simple linear regression
export class LinearRegression {
  slope: number;
  intercept: number;
  r2: number;

  constructor() {
    this.slope = 0;
    this.intercept = 0;
    this.r2 = 0;
  }

  fit(x: number[], y: number[]): void {
    const n = x.length;
    if (n < 2) return;
    const meanX = x.reduce((a, b) => a + b, 0) / n;
    const meanY = y.reduce((a, b) => a + b, 0) / n;

    let num = 0, denX = 0, denY = 0;
    for (let i = 0; i < n; i++) {
      const dx = x[i] - meanX;
      const dy = y[i] - meanY;
      num += dx * dy;
      denX += dx * dx;
      denY += dy * dy;
    }

    this.slope = denX > 0 ? num / denX : 0;
    this.intercept = meanY - this.slope * meanX;
    this.r2 = (denX > 0 && denY > 0) ? (num * num) / (denX * denY) : 0;
  }

  predict(x: number): number {
    return this.slope * x + this.intercept;
  }
}

// Statistical utilities
export function zScore(value: number, data: number[]): number {
  const n = data.length;
  if (n < 2) return 0;
  const mean = data.reduce((a, b) => a + b, 0) / n;
  const std = Math.sqrt(data.reduce((a, b) => a + (b - mean) ** 2, 0) / n);
  return std > 0 ? (value - mean) / std : 0;
}

export function normalize(data: number[]): number[] {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  return data.map(v => (v - min) / range);
}

export function movingAverage(data: number[], window: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < data.length; i++) {
    const start = Math.max(0, i - window + 1);
    const slice = data.slice(start, i + 1);
    result.push(slice.reduce((a, b) => a + b, 0) / slice.length);
  }
  return result;
}

export function rsi(prices: number[], period: number = 14): number {
  if (prices.length < period + 1) return 50;
  const changes: number[] = [];
  for (let i = 1; i < prices.length; i++) {
    changes.push(prices[i] - prices[i - 1]);
  }
  const recent = changes.slice(-period);
  const gains = recent.filter(c => c > 0);
  const losses = recent.filter(c => c < 0).map(Math.abs);
  const avgGain = gains.length > 0 ? gains.reduce((a, b) => a + b, 0) / period : 0;
  const avgLoss = losses.length > 0 ? losses.reduce((a, b) => a + b, 0) / period : 0.001;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}
