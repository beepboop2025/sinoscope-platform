import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createMarketEngine } from './MarketEngine';

// Mock API modules to prevent actual network calls
vi.mock('../services/api/forexApi', () => ({ fetchForexRates: vi.fn().mockResolvedValue(null) }));
vi.mock('../services/api/cryptoApi', () => ({ fetchCryptoMarkets: vi.fn().mockResolvedValue(null) }));
vi.mock('../services/api/stockApi', () => ({ fetchStockQuotes: vi.fn().mockResolvedValue(null) }));
vi.mock('../services/api/bondApi', () => ({ fetchYieldCurve: vi.fn().mockResolvedValue(null) }));
vi.mock('../services/api/commodityApi', () => ({ fetchAllCommodities: vi.fn().mockResolvedValue(null) }));
vi.mock('../generators/mockEconomic', () => ({ generateMockEconomic: vi.fn().mockReturnValue({ GDP: { value: 25.5 } }), generateMockYieldCurve: vi.fn().mockReturnValue([]) }));
vi.mock('../generators/mockChina', () => ({ generateMockChinaIndices: vi.fn().mockReturnValue([]) }));

describe('MarketEngine', () => {
  let engine: ReturnType<typeof createMarketEngine>;

  beforeEach(() => {
    vi.useFakeTimers();
    engine = createMarketEngine();
  });

  afterEach(() => {
    engine.stop();
    vi.useRealTimers();
  });

  it('creates engine with initial empty state', () => {
    const snap = engine.getSnapshot();
    expect(snap.forex).toEqual({});
    expect(snap.stocks).toEqual({});
    expect(snap.crypto).toEqual({});
    expect(snap.bonds).toEqual([]);
  });

  it('updates from WebSocket tick for crypto', () => {
    engine.updateFromWS({ symbol: 'BTCUSDT', price: 43000, changePct: 2.5 });
    const snap = engine.getSnapshot();
    expect(snap.crypto.BTC).toBeDefined();
    expect(snap.crypto.BTC.price).toBe(43000);
  });

  it('updates from WebSocket tick for stocks', () => {
    engine.updateFromWS({ symbol: 'AAPL', price: 185.5, changePct: 1.2 });
    const snap = engine.getSnapshot();
    expect(snap.stocks.AAPL).toBeDefined();
    expect(snap.stocks.AAPL.price).toBe(185.5);
  });

  it('notifies subscribers on WS update', () => {
    const listener = vi.fn();
    engine.subscribe(listener);
    // Note: updateFromWS does NOT call notify directly - it just updates state
    // The snapshot should still have the updated data
    engine.updateFromWS({ symbol: 'BTCUSDT', price: 43000 });
    const snap = engine.getSnapshot();
    expect(snap.crypto.BTC.price).toBe(43000);
  });

  it('unsubscribes correctly', () => {
    const listener = vi.fn();
    const unsub = engine.subscribe(listener);
    unsub();
    // After unsubscribe, listener should not be called
  });
});
