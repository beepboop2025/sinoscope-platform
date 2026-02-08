import { useState, useEffect, useRef, useCallback } from 'react';
import { MLEngine } from '../ml/MLEngine.js';

// Singleton ML engine instance
let engineInstance = null;

function getEngine() {
  if (!engineInstance) {
    engineInstance = new MLEngine();
  }
  return engineInstance;
}

export function useMLEngine(marketData) {
  const engineRef = useRef(getEngine());
  const [state, setState] = useState(() => engineRef.current.getState());

  // Subscribe to engine updates
  useEffect(() => {
    const engine = engineRef.current;
    const unsub = engine.subscribe(setState);
    return unsub;
  }, []);

  // Feed market data to engine
  useEffect(() => {
    if (marketData) {
      engineRef.current.ingest(marketData);
    }
  }, [marketData]);

  const forceRetrain = useCallback(() => {
    engineRef.current.forceRetrain();
  }, []);

  const reset = useCallback(() => {
    engineRef.current.reset();
  }, []);

  const getSignal = useCallback((symbol) => {
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
