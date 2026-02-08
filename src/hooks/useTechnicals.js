import { useState, useEffect, useRef, useCallback } from 'react';
import { createTechnicalEngine } from '../engine/TechnicalEngine';

/**
 * Hook that wraps TechnicalEngine — feeds it market data, exposes indicators/signals.
 * @param {Object} marketData - from useMarketData
 * @returns {Object} { indicators, signals, getIndicators, getSignals, getTrend }
 */
export function useTechnicals(marketData) {
  const engineRef = useRef(null);
  const [indicators, setIndicators] = useState({});
  const [signals, setSignals] = useState({});

  if (!engineRef.current) {
    engineRef.current = createTechnicalEngine();
  }

  // Feed market data as candles into TechnicalEngine
  useEffect(() => {
    if (!marketData) return;
    const engine = engineRef.current;
    const newIndicators = {};
    const newSignals = {};

    // Feed stock data
    for (const [sym, d] of Object.entries(marketData.stocks || {})) {
      const price = Number(d?.price) || 0;
      if (!price) continue;
      engine.addCandle(sym, {
        open: price, high: price * 1.001, low: price * 0.999,
        close: price, volume: d.volume || 0, timestamp: Date.now(),
      });
      const ind = engine.getIndicators(sym);
      if (ind) newIndicators[sym] = ind;
      const sig = engine.getSignals(sym);
      if (sig && sig.length > 0) newSignals[sym] = sig;
    }

    // Feed crypto data
    for (const [sym, d] of Object.entries(marketData.crypto || {})) {
      const price = Number(d?.price) || 0;
      if (!price) continue;
      const cleanSym = sym.replace('USDT', '');
      engine.addCandle(cleanSym, {
        open: price, high: price * 1.002, low: price * 0.998,
        close: price, volume: d.volume || 0, timestamp: Date.now(),
      });
      const ind = engine.getIndicators(cleanSym);
      if (ind) newIndicators[cleanSym] = ind;
      const sig = engine.getSignals(cleanSym);
      if (sig && sig.length > 0) newSignals[cleanSym] = sig;
    }

    if (Object.keys(newIndicators).length > 0) setIndicators(newIndicators);
    if (Object.keys(newSignals).length > 0) setSignals(newSignals);
  }, [marketData]);

  const getIndicators = useCallback((symbol) => {
    return engineRef.current.getIndicators(symbol);
  }, []);

  const getSignals = useCallback((symbol) => {
    return engineRef.current.getSignals(symbol);
  }, []);

  const getTrend = useCallback((symbol) => {
    return engineRef.current.getTrend(symbol);
  }, []);

  return { indicators, signals, getIndicators, getSignals, getTrend };
}
