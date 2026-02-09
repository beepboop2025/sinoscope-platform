import type { MarketTick } from '../types';

interface PortfolioHolding {
  symbol: string;
  quantity: number;
  avgCost: number;
  assetType: 'stock' | 'crypto' | 'etf';
}

interface HoldingPnL {
  cost: number;
  currentValue: number;
  pnl: number;
  pnlPct: number;
}

interface AllocationItem {
  symbol: string;
  value: number;
  assetType: string;
  pct: number;
}

interface TotalValueResult {
  totalValue: number;
  totalCost: number;
  totalPnL: number;
  totalPnLPct: number;
}

interface MarketDataMap {
  crypto?: Record<string, MarketTick>;
  stocks?: Record<string, MarketTick>;
}

export function calculateHoldingPnL(holding: PortfolioHolding, currentPrice: unknown): HoldingPnL {
  const cost = holding.quantity * holding.avgCost;
  const currentValue = holding.quantity * (Number(currentPrice) || 0);
  const pnl = currentValue - cost;
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
  return { cost, currentValue, pnl, pnlPct };
}

export function calculateAllocation(holdings: PortfolioHolding[], marketData: MarketDataMap | null): AllocationItem[] {
  const items = holdings.map(h => {
    const price = getPrice(h.symbol, h.assetType, marketData);
    const value = h.quantity * (Number(price) || h.avgCost);
    return { symbol: h.symbol, value, assetType: h.assetType };
  });
  const total = items.reduce((s, i) => s + i.value, 0);
  return items.map(i => ({ ...i, pct: total > 0 ? (i.value / total) * 100 : 0 }));
}

export function calculateTotalValue(holdings: PortfolioHolding[], marketData: MarketDataMap | null): TotalValueResult {
  let totalValue = 0;
  let totalCost = 0;
  for (const h of holdings) {
    const price = getPrice(h.symbol, h.assetType, marketData);
    totalValue += h.quantity * (Number(price) || h.avgCost);
    totalCost += h.quantity * h.avgCost;
  }
  const totalPnL = totalValue - totalCost;
  const totalPnLPct = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;
  return { totalValue, totalCost, totalPnL, totalPnLPct };
}

function getPrice(symbol: string, assetType: string, marketData: MarketDataMap | null): number {
  if (!marketData) return 0;
  if (assetType === 'crypto') {
    const d = marketData.crypto?.[symbol] || marketData.crypto?.[symbol + 'USDT'];
    return d?.price || 0;
  }
  const d = marketData.stocks?.[symbol];
  return d?.price || 0;
}
