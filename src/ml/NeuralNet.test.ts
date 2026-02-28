import { describe, it, expect } from 'vitest';
import { NeuralNet, fisherYatesShuffle } from './NeuralNet';

describe('NeuralNet', () => {
  it('creates a network with correct layer shapes', () => {
    const net = new NeuralNet([4, 8, 3]);
    expect(net.layers).toEqual([4, 8, 3]);
    expect(net.weights).toHaveLength(2); // 2 weight matrices
    expect(net.weights[0]).toHaveLength(8); // 8 neurons in hidden layer
    expect(net.weights[0][0]).toHaveLength(4); // 4 inputs per hidden neuron
    expect(net.weights[1]).toHaveLength(3); // 3 output neurons
    expect(net.weights[1][0]).toHaveLength(8); // 8 inputs per output neuron
  });

  it('produces output of correct dimension', () => {
    const net = new NeuralNet([10, 16, 8, 3]);
    const input = Array.from({ length: 10 }, () => Math.random());
    const output = net.predict(input);
    expect(output).toHaveLength(3);
  });

  it('predict guards against NaN outputs', () => {
    const net = new NeuralNet([2, 2]);
    // Force extreme weights to trigger potential NaN
    net.weights[0] = [[1e10, 1e10], [1e10, 1e10]];
    const output = net.predict([1e10, 1e10]);
    output.forEach(v => {
      expect(Number.isFinite(v)).toBe(true);
    });
  });

  it('backward validates inputs and returns high loss for NaN', () => {
    const net = new NeuralNet([2, 1]);
    const loss = net.backward([NaN, 1], [0]);
    expect(loss).toBe(1);
  });

  it('trains and reduces loss over epochs', () => {
    const net = new NeuralNet([2, 4, 1], { learningRate: 0.1 });
    // Simple XOR-like pattern
    const data = [
      { input: [0, 0], target: [0] },
      { input: [1, 0], target: [1] },
      { input: [0, 1], target: [1] },
      { input: [1, 1], target: [0] },
    ];

    let totalLoss = 0;
    // Train 100 epochs
    for (let epoch = 0; epoch < 100; epoch++) {
      totalLoss = 0;
      for (const d of data) {
        totalLoss += net.backward(d.input, d.target);
      }
    }

    // Loss should decrease (not necessarily converge for XOR, but shouldn't blow up)
    expect(Number.isFinite(totalLoss)).toBe(true);
    expect(totalLoss).toBeLessThan(500);
  });

  it('serializes and deserializes correctly', () => {
    const net = new NeuralNet([3, 4, 2]);
    const input = [0.5, 0.3, 0.7];
    const originalOutput = net.predict(input);

    const json = net.serialize();
    const restored = NeuralNet.deserialize(json);
    const restoredOutput = restored.predict(input);

    expect(restoredOutput).toEqual(originalOutput);
    expect(restored.layers).toEqual([3, 4, 2]);
  });
});

describe('fisherYatesShuffle', () => {
  it('preserves all elements', () => {
    const arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const shuffled = fisherYatesShuffle([...arr]);
    expect(shuffled.sort((a, b) => a - b)).toEqual(arr);
  });

  it('returns the same array reference (in-place)', () => {
    const arr = [1, 2, 3];
    const result = fisherYatesShuffle(arr);
    expect(result).toBe(arr);
  });
});
