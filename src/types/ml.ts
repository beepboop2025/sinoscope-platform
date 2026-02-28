export interface NeuralNetConfig {
  layers: number[];
  learningRate: number;
  activation?: 'relu' | 'sigmoid' | 'tanh';
}

export interface TrainingDataPoint {
  input: number[];
  target: number[];
}

export interface TrainingStatus {
  isTraining: boolean;
  epoch: number;
  totalEpochs: number;
  trainLoss: number;
  valLoss: number;
  lastTrainTime: number;
  dataPoints: number;
}

export interface MLPrediction {
  symbol: string;
  predicted: number;
  confidence: number;
  direction: 'up' | 'down' | 'neutral';
  timestamp: number;
}

export interface MLAnomaly {
  id: string;
  type: 'ml_anomaly';
  symbol: string;
  score: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: number;
}

export interface MLSignal {
  symbol: string;
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  reasons: string[];
  timestamp: number;
}

export interface MLMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
}

export interface MLModelInfo {
  name: string;
  type: string;
  trained: boolean;
  metrics: MLMetrics | null;
  lastTrainTime: number;
}

export interface MLState {
  training: TrainingStatus;
  predictions: MLPrediction[];
  anomalies: MLAnomaly[];
  signals: MLSignal[];
  models: MLModelInfo[];
  regime: string;
  features: number;
}

export type MarketRegimeType = 'bull' | 'bear' | 'volatile' | 'ranging' | 'unknown';
