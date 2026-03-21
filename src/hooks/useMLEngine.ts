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
  workerActive: boolean;
}

// ── Web Worker singleton ─────────────────────────────────────────────────────
let mlWorker: Worker | null = null;
let workerReady = false;
let pendingCallbacks: Map<string, { resolve: (v: unknown) => void; reject: (e: Error) => void }> = new Map();
let msgCounter = 0;

function getMLWorker(): Worker | null {
  if (mlWorker) return mlWorker;
  try {
    mlWorker = new Worker(
      new URL('../workers/mlWorker.ts', import.meta.url),
      { type: 'module' }
    );
    mlWorker.addEventListener('message', (e) => {
      const { type, payload, id, error } = e.data;
      if (type === 'ready') { workerReady = true; return; }
      const cb = pendingCallbacks.get(id);
      if (cb) {
        pendingCallbacks.delete(id);
        if (error) cb.reject(new Error(error));
        else cb.resolve(payload);
      }
    });
    mlWorker.addEventListener('error', () => {
      console.warn('[mlWorker] Worker error — falling back to main thread');
      mlWorker = null;
      workerReady = false;
    });
    return mlWorker;
  } catch {
    console.warn('[mlWorker] Web Workers not supported — ML runs on main thread');
    return null;
  }
}

function postToWorker(type: string, payload: unknown): Promise<unknown> {
  const worker = getMLWorker();
  if (!worker) return Promise.reject(new Error('Worker unavailable'));
  const id = `msg_${++msgCounter}_${Date.now()}`;
  return new Promise((resolve, reject) => {
    pendingCallbacks.set(id, { resolve, reject });
    worker.postMessage({ type, payload, id });
    // Timeout after 30s to prevent hanging
    setTimeout(() => {
      if (pendingCallbacks.has(id)) {
        pendingCallbacks.delete(id);
        reject(new Error('Worker timeout'));
      }
    }, 30000);
  });
}

// ── Singleton ML engine instance — shared across all hook consumers ──────────
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
  const [workerActive, setWorkerActive] = useState(false);

  // Initialize worker on mount
  useEffect(() => {
    const worker = getMLWorker();
    setWorkerActive(!!worker);
    return () => {
      // Don't terminate the shared worker on unmount — other hooks may use it
    };
  }, []);

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
    const engine = engineRef.current;
    // Try offloading anomaly detection to the worker (lightweight operation)
    // Full training still runs on the main thread via the engine's own train()
    // because the engine manages data buffers that can't be serialized cheaply.
    // The worker is used for predict/detectAnomalies when called explicitly.
    engine.forceRetrain();
  }, []);

  const reset = useCallback((): void => {
    engineRef.current.reset();
    if (workerReady) {
      postToWorker('reset', {}).catch(() => { /* ignore */ });
    }
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
    workerActive,
  };
}
