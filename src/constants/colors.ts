export const HEATMAP_COLORS = {
  strongNegative: '#ef4444',
  negative: '#f87171',
  weakNegative: '#fca5a5',
  neutral: '#1e293b',
  weakPositive: '#86efac',
  positive: '#4ade80',
  strongPositive: '#22c55e',
};

export const correlationColor = (value) => {
  if (value >= 0.8) return HEATMAP_COLORS.strongPositive;
  if (value >= 0.5) return HEATMAP_COLORS.positive;
  if (value >= 0.2) return HEATMAP_COLORS.weakPositive;
  if (value > -0.2) return HEATMAP_COLORS.neutral;
  if (value > -0.5) return HEATMAP_COLORS.weakNegative;
  if (value > -0.8) return HEATMAP_COLORS.negative;
  return HEATMAP_COLORS.strongNegative;
};

export const priceChangeColor = (v) => {
  const n = Number(v) || 0;
  if (n > 0) return 'var(--green)';
  if (n < 0) return 'var(--red)';
  return 'var(--text-2)';
};

export const CHART_COLORS = [
  '#06d6e0', '#a78bfa', '#10b981', '#f59e0b', '#ef4444',
  '#3b82f6', '#fb923c', '#ec4899', '#14b8a6', '#64748b',
];
