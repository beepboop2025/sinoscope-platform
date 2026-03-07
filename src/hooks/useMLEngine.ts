import { useState, useEffect, useRef, useCallback } from 'react';
import { MLEngine } from '../ml/MLEngine';
import type { MarketSnapshot } from '../types';

interface MLEngineState {
  trainingStatus: {
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
  };
  predictions: Record<string, unknown>;
  signals: unknown[];
  signalSummary: unknown;
  anomalies: unknown[];
  anomalyStats: unknown;
  trackedSymbols: number;
  dataPoints: number;
  trainLoss: number[];
}

interface UseMLEngineReturn extends MLEngineState {
  forceRetrain: () => void;
  reset: () => void;
  getSignal: (symbol: string) => unknown;
  isReady: boolean;
}

// Singleton ML engine instance — shared across all hook consumers
let engineInstance: MLEngine | null = null;
let refCount = 0;

function getEngine(): MLEngine {
  if (!engineInstance) {
    engineInstance = new MLEngine();
  }
  refCount++;
  return engineInstance;
}

function releaseEngine(): void {
  refCount--;
  if (refCount <= 0 && engineInstance) {
    engineInstance.destroy();
    engineInstance = null;
    refCount = 0;
  }
}

export function useMLEngine(marketData: MarketSnapshot | null): UseMLEngineReturn {
  const engineRef = useRef<MLEngine>(getEngine());
  const [state, setState] = useState<MLEngineState>(() => engineRef.current.getState());

  // Subscribe to engine updates and release on unmount
  useEffect(() => {
    const engine = engineRef.current;
    const unsub = engine.subscribe(setState);
    return () => {
      unsub();
      releaseEngine();
    };
  }, []);

  // Feed market data to engine
  useEffect(() => {
    if (marketData) {
      engineRef.current.ingest(marketData);
    }
  }, [marketData]);

  const forceRetrain = useCallback((): void => {
    engineRef.current.forceRetrain();
  }, []);

  const reset = useCallback((): void => {
    engineRef.current.reset();
  }, []);

  const getSignal = useCallback((symbol: string): unknown => {
    return engineRef.current.predictions[symbol] || null;
  }, []);

  return {
    ...state,
    forceRetrain,
    reset,
    getSignal,
    isReady: state.trackedSymbols > 0,
  };
}
