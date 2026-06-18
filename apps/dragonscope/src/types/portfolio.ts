export interface Holding {
  id: string;
  symbol: string;
  shares: number;
  avgCost: number;
  type: 'stock' | 'crypto' | 'etf';
}

export interface Portfolio {
  id: string;
  name: string;
  holdings: Holding[];
  createdAt?: number;
}

export interface AllocationItem {
  symbol: string;
  value: number;
  percentage: number;
  color: string;
}

export interface PnLResult {
  symbol: string;
  shares: number;
  avgCost: number;
  currentPrice: number;
  costBasis: number;
  marketValue: number;
  pnl: number;
  pnlPct: number;
}

export interface PortfolioSummary {
  totalValue: number;
  totalCost: number;
  totalPnL: number;
  totalPnLPct: number;
  holdings: PnLResult[];
  allocation: AllocationItem[];
}
