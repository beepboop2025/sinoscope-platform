export function normalizeTick(raw, market) {
  return {
    symbol: raw.symbol || raw.s || '',
    price: Number(raw.price ?? raw.c ?? raw.p ?? 0),
    change: Number(raw.change ?? raw.d ?? 0),
    changePct: Number(raw.changePct ?? raw.dp ?? raw.changesPercentage ?? 0),
    volume: Number(raw.volume ?? raw.v ?? 0),
    high: Number(raw.high ?? raw.h ?? 0),
    low: Number(raw.low ?? raw.l ?? 0),
    open: Number(raw.open ?? raw.o ?? 0),
    timestamp: raw.timestamp ?? raw.t ?? Date.now(),
    market,
  };
}

export function normalizeForex(pair, data) {
  const rate = Number(data) || 0;
  return {
    symbol: pair,
    price: rate,
    change: 0,
    changePct: 0,
    volume: 0,
    high: rate,
    low: rate,
    open: rate,
    timestamp: Date.now(),
    market: 'forex',
  };
}

export function normalizeCrypto(data) {
  return {
    symbol: (data.symbol || data.id || '').toUpperCase(),
    name: data.name || '',
    price: Number(data.current_price ?? data.price ?? 0),
    change: Number(data.price_change_24h ?? 0),
    changePct: Number(data.price_change_percentage_24h ?? 0),
    volume: Number(data.total_volume ?? 0),
    marketCap: Number(data.market_cap ?? 0),
    high: Number(data.high_24h ?? 0),
    low: Number(data.low_24h ?? 0),
    timestamp: Date.now(),
    market: 'crypto',
  };
}

export function normalizeOHLC(data) {
  return {
    time: data.t || data.date || data.timestamp,
    open: Number(data.o ?? data.open ?? 0),
    high: Number(data.h ?? data.high ?? 0),
    low: Number(data.l ?? data.low ?? 0),
    close: Number(data.c ?? data.close ?? 0),
    volume: Number(data.v ?? data.volume ?? 0),
  };
}
