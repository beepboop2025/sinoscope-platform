/**
 * TimelineEngine - Event-market overlay analysis
 * Maps news/events to price movements
 */

interface TimelineEvent {
  id: string;
  type: string;
  title: string;
  timestamp: number;
  symbols: string[];
  impact: string;
  source: string;
  addedAt?: number;
}

interface PriceCapture {
  symbol: string;
  timestamp: number;
  price: number;
  capturedAt: number;
}

interface PriceHistoryPoint {
  timestamp: number;
  price: number;
}

interface ImpactWindow {
  change: number;
  direction: 'up' | 'down' | 'neutral';
  magnitude: number;
}

interface ImpactAnalysis {
  eventId: string;
  symbol: string;
  eventTime: number;
  eventPrice: number;
  impacts: Record<string, ImpactWindow>;
}

interface VolatilityDataPoint {
  timestamp: number;
  volatility: number;
}

interface VolatilityEventCorrelation {
  timestamp: number;
  volatility: number;
  events: TimelineEvent[];
}

interface MarketRegimeInfo {
  regime: string;
  eventCount: number;
  typeDistribution: Record<string, number>;
  impactDistribution: Record<string, number>;
  window: number;
}

interface TimelineEngineInstance {
  addEvent(event: Omit<TimelineEvent, 'addedAt'>): void;
  capturePriceAtEvent(symbol: string, timestamp: number, price: number): void;
  calculateImpact(eventId: string, symbol: string, priceHistory: PriceHistoryPoint[], windows?: number[]): ImpactAnalysis | null;
  getEventsForSymbol(symbol: string, startTime: number, endTime: number): TimelineEvent[];
  getEventsByType(type: string, limit?: number): TimelineEvent[];
  getHighImpactEvents(limit?: number): TimelineEvent[];
  createTimeline(startTime: number, endTime: number, symbols?: string[]): TimelineEvent[];
  findVolatilityEvents(volatilityData: VolatilityDataPoint[], threshold?: number): VolatilityEventCorrelation[];
  getMarketRegime(window?: number): MarketRegimeInfo;
  clear(): void;
}

/**
 * Create TimelineEngine instance
 */
export function createTimelineEngine(): TimelineEngineInstance {
  const events: TimelineEvent[] = [];
  const priceData = new Map<string, PriceCapture>();

  /**
   * Add event to timeline
   */
  function addEvent(event: Omit<TimelineEvent, 'addedAt'>): void {
    events.push({
      ...event,
      addedAt: Date.now(),
    });
  }

  /**
   * Store price snapshot at event time
   */
  function capturePriceAtEvent(symbol: string, timestamp: number, price: number): void {
    const key = `${symbol}-${timestamp}`;
    priceData.set(key, {
      symbol,
      timestamp,
      price,
      capturedAt: Date.now(),
    });
  }

  /**
   * Calculate price impact of an event
   */
  function calculateImpact(eventId: string, symbol: string, priceHistory: PriceHistoryPoint[], windows: number[] = [5, 30, 60]): ImpactAnalysis | null {
    const event = events.find(e => e.id === eventId);
    if (!event) return null;

    const eventTime = event.timestamp;
    const eventPrice = priceHistory.find(p => p.timestamp >= eventTime)?.price;

    if (!eventPrice) return null;

    const impacts: Record<string, ImpactWindow> = {};

    windows.forEach(window => {
      const futureTime = eventTime + window * 60 * 1000;
      const futurePrice = priceHistory.find(p => p.timestamp >= futureTime)?.price;

      if (futurePrice) {
        const change = ((futurePrice - eventPrice) / eventPrice) * 100;
        impacts[`${window}m`] = {
          change,
          direction: change > 0 ? 'up' : change < 0 ? 'down' : 'neutral',
          magnitude: Math.abs(change),
        };
      }
    });

    return {
      eventId,
      symbol,
      eventTime,
      eventPrice,
      impacts,
    };
  }

  /**
   * Get events affecting a symbol within time range
   */
  function getEventsForSymbol(symbol: string, startTime: number, endTime: number): TimelineEvent[] {
    return events.filter(e =>
      e.symbols.includes(symbol) &&
      e.timestamp >= startTime &&
      e.timestamp <= endTime
    );
  }

  /**
   * Get events by type
   */
  function getEventsByType(type: string, limit: number = 20): TimelineEvent[] {
    return events
      .filter(e => e.type === type)
      .slice(-limit)
      .reverse();
  }

  /**
   * Get high impact events
   */
  function getHighImpactEvents(limit: number = 10): TimelineEvent[] {
    return events
      .filter(e => e.impact === 'high')
      .slice(-limit)
      .reverse();
  }

  /**
   * Create timeline for visualization
   */
  function createTimeline(startTime: number, endTime: number, symbols: string[] = []): TimelineEvent[] {
    const filtered = events.filter(e => {
      const inTimeRange = e.timestamp >= startTime && e.timestamp <= endTime;
      const hasSymbol = symbols.length === 0 || e.symbols.some(s => symbols.includes(s));
      return inTimeRange && hasSymbol;
    });

    return filtered.sort((a, b) => a.timestamp - b.timestamp);
  }

  /**
   * Correlate events with volatility spikes
   */
  function findVolatilityEvents(volatilityData: VolatilityDataPoint[], threshold: number = 50): VolatilityEventCorrelation[] {
    const spikes = volatilityData.filter(v => v.volatility > threshold);
    const correlations: VolatilityEventCorrelation[] = [];

    spikes.forEach(spike => {
      // Find events within 1 hour of volatility spike
      const nearby = events.filter(e =>
        Math.abs(e.timestamp - spike.timestamp) < 60 * 60 * 1000
      );

      if (nearby.length > 0) {
        correlations.push({
          timestamp: spike.timestamp,
          volatility: spike.volatility,
          events: nearby,
        });
      }
    });

    return correlations;
  }

  /**
   * Get market regime based on event clustering
   */
  function getMarketRegime(window: number = 24): MarketRegimeInfo {
    const cutoff = Date.now() - window * 60 * 60 * 1000;
    const recent = events.filter(e => e.timestamp > cutoff);

    const typeCounts: Record<string, number> = {};
    const impactCounts: Record<string, number> = { high: 0, medium: 0, low: 0 };

    recent.forEach(e => {
      typeCounts[e.type] = (typeCounts[e.type] || 0) + 1;
      impactCounts[e.impact]++;
    });

    let regime = 'normal';
    if (impactCounts.high > 3) regime = 'high_volatility';
    else if (typeCounts.geopolitical > 2) regime = 'geopolitical_risk';
    else if (typeCounts.earnings > 5) regime = 'earnings_season';

    return {
      regime,
      eventCount: recent.length,
      typeDistribution: typeCounts,
      impactDistribution: impactCounts,
      window,
    };
  }

  /**
   * Clear all data
   */
  function clear(): void {
    events.length = 0;
    priceData.clear();
  }

  return {
    addEvent,
    capturePriceAtEvent,
    calculateImpact,
    getEventsForSymbol,
    getEventsByType,
    getHighImpactEvents,
    createTimeline,
    findVolatilityEvents,
    getMarketRegime,
    clear,
  };
}

export default createTimelineEngine;
