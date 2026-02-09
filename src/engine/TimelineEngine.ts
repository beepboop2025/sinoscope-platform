/**
 * TimelineEngine - Event-market overlay analysis
 * Maps news/events to price movements
 */

/**
 * Create TimelineEngine instance
 * @returns {Object} Engine methods
 */
export function createTimelineEngine() {
  const events = [];
  const priceData = new Map();

  /**
   * Add event to timeline
   * @param {Object} event - Event data
   * @param {string} event.id - Unique ID
   * @param {string} event.type - Event type (earnings, economic, geopolitical, etc.)
   * @param {string} event.title - Event title
   * @param {number} event.timestamp - Unix timestamp
   * @param {Array<string>} event.symbols - Affected symbols
   * @param {string} event.impact - Expected impact (high, medium, low)
   * @param {string} event.source - News source
   */
  function addEvent(event) {
    events.push({
      ...event,
      addedAt: Date.now(),
    });
  }

  /**
   * Store price snapshot at event time
   * @param {string} symbol - Ticker symbol
   * @param {number} timestamp - Event timestamp
   * @param {number} price - Price at event time
   */
  function capturePriceAtEvent(symbol, timestamp, price) {
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
   * @param {string} eventId - Event ID
   * @param {string} symbol - Symbol to analyze
   * @param {Array<Object>} priceHistory - Price history [{timestamp, price}]
   * @param {Array<number>} windows - Time windows in minutes [immediate, short, medium]
   * @returns {Object} Impact analysis
   */
  function calculateImpact(eventId, symbol, priceHistory, windows = [5, 30, 60]) {
    const event = events.find(e => e.id === eventId);
    if (!event) return null;
    
    const eventTime = event.timestamp;
    const eventPrice = priceHistory.find(p => p.timestamp >= eventTime)?.price;
    
    if (!eventPrice) return null;
    
    const impacts = {};
    
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
   * @param {string} symbol - Ticker symbol
   * @param {number} startTime - Start timestamp
   * @param {number} endTime - End timestamp
   * @returns {Array} Matching events
   */
  function getEventsForSymbol(symbol, startTime, endTime) {
    return events.filter(e => 
      e.symbols.includes(symbol) &&
      e.timestamp >= startTime &&
      e.timestamp <= endTime
    );
  }

  /**
   * Get events by type
   * @param {string} type - Event type
   * @param {number} limit - Max results
   * @returns {Array} Events
   */
  function getEventsByType(type, limit = 20) {
    return events
      .filter(e => e.type === type)
      .slice(-limit)
      .reverse();
  }

  /**
   * Get high impact events
   * @param {number} limit - Max results
   * @returns {Array} High impact events
   */
  function getHighImpactEvents(limit = 10) {
    return events
      .filter(e => e.impact === 'high')
      .slice(-limit)
      .reverse();
  }

  /**
   * Create timeline for visualization
   * @param {number} startTime - Start timestamp
   * @param {number} endTime - End timestamp
   * @param {Array<string>} symbols - Symbols to include
   * @returns {Array} Timeline events
   */
  function createTimeline(startTime, endTime, symbols = []) {
    const filtered = events.filter(e => {
      const inTimeRange = e.timestamp >= startTime && e.timestamp <= endTime;
      const hasSymbol = symbols.length === 0 || e.symbols.some(s => symbols.includes(s));
      return inTimeRange && hasSymbol;
    });
    
    return filtered.sort((a, b) => a.timestamp - b.timestamp);
  }

  /**
   * Correlate events with volatility spikes
   * @param {Array<Object>} volatilityData - [{timestamp, volatility}]
   * @param {number} threshold - Volatility threshold
   * @returns {Array} Correlated events
   */
  function findVolatilityEvents(volatilityData, threshold = 50) {
    const spikes = volatilityData.filter(v => v.volatility > threshold);
    const correlations = [];
    
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
   * @param {number} window - Time window in hours
   * @returns {Object} Market regime info
   */
  function getMarketRegime(window = 24) {
    const cutoff = Date.now() - window * 60 * 60 * 1000;
    const recent = events.filter(e => e.timestamp > cutoff);
    
    const typeCounts = {};
    const impactCounts = { high: 0, medium: 0, low: 0 };
    
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
  function clear() {
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
