import { useState, useRef, useCallback } from 'react';
import { createTechnicalEngine } from '../engine/TechnicalEngine';

export function useTechnicals() {
  const engineRef = useRef(createTechnicalEngine());
  const [indicators, setIndicators] = useState(null);

  const compute = useCallback((symbol, prices) => {
    const result = engineRef.current.compute(symbol, prices);
    setIndicators(result);
    return result;
  }, []);

  const getSignal = useCallback((rsiValue) => {
    return engineRef.current.getSignal(rsiValue);
  }, []);

  return { indicators, compute, getSignal };
}
