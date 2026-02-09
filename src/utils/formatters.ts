export const formatPrice = (v: unknown, decimals: number = 2): string => {
  const n = Number(v) || 0;
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(2)}K`;
  return n.toFixed(decimals);
};

export const formatPct = (v: unknown): string => `${(Number(v) || 0).toFixed(2)}%`;

export const formatVolume = (v: unknown): string => {
  const n = Number(v) || 0;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(0);
};

export const formatBps = (v: unknown): string => `${(Number(v) || 0).toFixed(0)}bps`;

export const formatCurrency = (v: unknown, currency: string = 'USD'): string => {
  const n = Number(v) || 0;
  const symbols: Record<string, string> = { USD: '$', EUR: '\u20AC', GBP: '\u00A3', JPY: '\u00A5', CNY: '\u00A5', INR: '\u20B9' };
  return `${symbols[currency] || ''}${formatPrice(n)}`;
};

export const formatChange = (v: unknown): string => {
  const n = Number(v) || 0;
  return n >= 0 ? `+${n.toFixed(2)}` : n.toFixed(2);
};

export const formatChangePct = (v: unknown): string => {
  const n = Number(v) || 0;
  return n >= 0 ? `+${n.toFixed(2)}%` : `${n.toFixed(2)}%`;
};
