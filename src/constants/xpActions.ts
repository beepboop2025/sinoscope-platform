export const XP_ACTIONS: Record<string, { xp: number; label: string }> = {
  workspace_switch: { xp: 5, label: 'Switched workspace' },
  command_bar_use: { xp: 3, label: 'Used command bar' },
  sql_query: { xp: 10, label: 'Ran SQL query' },
  panel_add: { xp: 8, label: 'Added panel' },
  watchlist_add: { xp: 5, label: 'Added to watchlist' },
  chart_export: { xp: 10, label: 'Exported chart' },
  ml_train: { xp: 25, label: 'Trained ML model' },
  prediction_create: { xp: 15, label: 'Made prediction' },
  prediction_correct: { xp: 50, label: 'Correct prediction' },
  theme_switch: { xp: 2, label: 'Switched theme' },
  daily_login: { xp: 20, label: 'Daily login' },
  streak_bonus: { xp: 10, label: 'Streak day bonus' },
  symbol_link: { xp: 5, label: 'Linked panel to symbol' },
};

// Level thresholds: level -> cumulative XP required
export const LEVEL_THRESHOLDS = [0, 100, 500, 2000, 5000, 10000, 20000, 50000, 100000, 200000] as const;

export function getLevelForXP(xp: number): number {
  for (let i = LEVEL_THRESHOLDS.length - 1; i >= 0; i--) {
    if (xp >= LEVEL_THRESHOLDS[i]) return i + 1;
  }
  return 1;
}

export function getXPForNextLevel(xp: number): { current: number; next: number; progress: number } {
  const level = getLevelForXP(xp);
  const currentThreshold = LEVEL_THRESHOLDS[level - 1] || 0;
  const nextThreshold = LEVEL_THRESHOLDS[level] || LEVEL_THRESHOLDS[LEVEL_THRESHOLDS.length - 1] * 2;
  const progress = (xp - currentThreshold) / (nextThreshold - currentThreshold);
  return { current: currentThreshold, next: nextThreshold, progress: Math.min(1, Math.max(0, progress)) };
}
