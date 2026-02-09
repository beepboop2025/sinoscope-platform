import { describe, it, expect, beforeEach } from 'vitest';
import { createTimelineEngine } from './TimelineEngine';

describe('TimelineEngine', () => {
  let timeline;

  beforeEach(() => {
    timeline = createTimelineEngine();
  });

  it('adds and retrieves events', () => {
    timeline.addEvent({
      id: 'test1', type: 'earnings', title: 'AAPL beat estimates',
      timestamp: Date.now(), symbols: ['AAPL'], impact: 'high', source: 'test',
    });
    const events = timeline.createTimeline(Date.now() - 60000, Date.now() + 60000);
    expect(events).toHaveLength(1);
    expect(events[0].title).toBe('AAPL beat estimates');
  });

  it('filters events by symbol', () => {
    timeline.addEvent({ id: 'e1', type: 'economic', title: 'Fed rate', timestamp: Date.now(), symbols: ['SPX'], impact: 'high', source: 'test' });
    timeline.addEvent({ id: 'e2', type: 'earnings', title: 'AAPL', timestamp: Date.now(), symbols: ['AAPL'], impact: 'medium', source: 'test' });
    const events = timeline.getEventsForSymbol('AAPL', Date.now() - 60000, Date.now() + 60000);
    expect(events).toHaveLength(1);
    expect(events[0].id).toBe('e2');
  });

  it('gets events by type', () => {
    timeline.addEvent({ id: 'e1', type: 'earnings', title: 'A', timestamp: Date.now(), symbols: [], impact: 'low', source: 'test' });
    timeline.addEvent({ id: 'e2', type: 'economic', title: 'B', timestamp: Date.now(), symbols: [], impact: 'low', source: 'test' });
    timeline.addEvent({ id: 'e3', type: 'earnings', title: 'C', timestamp: Date.now(), symbols: [], impact: 'low', source: 'test' });
    const earnings = timeline.getEventsByType('earnings');
    expect(earnings).toHaveLength(2);
  });

  it('gets high impact events', () => {
    timeline.addEvent({ id: 'e1', type: 'earnings', title: 'Low', timestamp: Date.now(), symbols: [], impact: 'low', source: 'test' });
    timeline.addEvent({ id: 'e2', type: 'earnings', title: 'High', timestamp: Date.now(), symbols: [], impact: 'high', source: 'test' });
    const high = timeline.getHighImpactEvents();
    expect(high).toHaveLength(1);
    expect(high[0].title).toBe('High');
  });

  it('captures price at event', () => {
    timeline.capturePriceAtEvent('AAPL', Date.now(), 185.5);
    // Price capture is stored internally - no direct getter exposed but no error thrown
  });

  it('calculates impact from price history', () => {
    const now = Date.now();
    timeline.addEvent({ id: 'ev1', type: 'earnings', title: 'AAPL', timestamp: now, symbols: ['AAPL'], impact: 'high', source: 'test' });
    const history = [
      { timestamp: now, price: 100 },
      { timestamp: now + 5 * 60 * 1000, price: 105 },
      { timestamp: now + 30 * 60 * 1000, price: 110 },
      { timestamp: now + 60 * 60 * 1000, price: 108 },
    ];
    const impact = timeline.calculateImpact('ev1', 'AAPL', history);
    expect(impact).not.toBeNull();
    expect(impact.impacts['5m'].change).toBeCloseTo(5, 0);
    expect(impact.impacts['30m'].change).toBeCloseTo(10, 0);
  });

  it('gets market regime', () => {
    const regime = timeline.getMarketRegime(24);
    expect(regime.regime).toBe('normal');
    expect(regime.eventCount).toBe(0);
  });

  it('clears all data', () => {
    timeline.addEvent({ id: 'e1', type: 'test', title: 'Test', timestamp: Date.now(), symbols: [], impact: 'low', source: 'test' });
    timeline.clear();
    const events = timeline.createTimeline(0, Date.now() + 60000);
    expect(events).toHaveLength(0);
  });
});
