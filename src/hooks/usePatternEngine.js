import { useState, useEffect, useRef, useCallback } from 'react';
import { createPatternEngine } from '../engine/PatternEngine';

/**
 * Hook that wraps PatternEngine — feeds it market data, exposes anomalies/events.
 * @param {Object} marketData - from useMarketData
 * @returns {Object} { events, getSymbolEvents, clear }
 */
export function usePatternEngine(marketData) {
  const engineRef = useRef(null);
  const prevPricesRef = useRef({});
  const [events, setEvents] = useState([]);

  if (!engineRef.current) {
    engineRef.current = createPatternEngine();
  }

  // Feed market data into PatternEngine and collect anomalies
  useEffect(() => {
    if (!marketData) return;
    const engine = engineRef.current;
    const prev = prevPricesRef.current;
    const newEvents = [];

    // Check stocks for price anomalies
    for (const [sym, d] of Object.entries(marketData.stocks || {})) {
      const price = Number(d?.price) || 0;
      if (!price) continue;
      if (prev[sym]) {
        const anomaly = engine.detectPriceAnomaly(sym, price, prev[sym]);
        if (anomaly) newEvents.push(anomaly);
      }
      if (d.volume && d.avgVolume) {
        const volAnomaly = engine.detectVolumeAnomaly(sym, d.volume, d.avgVolume);
        if (volAnomaly) newEvents.push(volAnomaly);
      }
      prev[sym] = price;
    }

    // Check crypto for price anomalies
    for (const [sym, d] of Object.entries(marketData.crypto || {})) {
      const price = Number(d?.price) || 0;
      if (!price) continue;
      const key = `crypto_${sym}`;
      if (prev[key]) {
        const anomaly = engine.detectPriceAnomaly(sym.replace('USDT', ''), price, prev[key]);
        if (anomaly) newEvents.push(anomaly);
      }
      prev[key] = price;
    }

    // Check forex for price anomalies
    for (const [sym, d] of Object.entries(marketData.forex || {})) {
      const price = Number(d?.price || d?.rate) || 0;
      if (!price) continue;
      const key = `fx_${sym}`;
      if (prev[key]) {
        const anomaly = engine.detectPriceAnomaly(sym, price, prev[key]);
        if (anomaly) newEvents.push(anomaly);
      }
      prev[key] = price;
    }

    if (newEvents.length > 0) {
      setEvents(engine.getRecentEvents(50));
    }
    prevPricesRef.current = prev;
  }, [marketData]);

  const getSymbolEvents = useCallback((symbol) => {
    return engineRef.current.getSymbolEvents(symbol);
  }, []);

  const clear = useCallback(() => {
    engineRef.current.clear();
    setEvents([]);
  }, []);

  return { events, getSymbolEvents, clear };
}
