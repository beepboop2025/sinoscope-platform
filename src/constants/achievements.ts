export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  xpReward: number;
  condition: string;
}

export const ACHIEVEMENTS: Achievement[] = [
  { id: 'first_login', name: 'First Steps', description: 'Open DragonScope for the first time', icon: '🚀', xpReward: 50, condition: 'login' },
  { id: 'workspace_explorer', name: 'Workspace Explorer', description: 'Visit all 9 workspaces', icon: '🗺️', xpReward: 100, condition: 'all_workspaces' },
  { id: 'command_master', name: 'Command Master', description: 'Use the command bar 10 times', icon: '⌨️', xpReward: 75, condition: 'command_bar_10' },
  { id: 'data_hunter', name: 'Data Hunter', description: 'Run your first SQL query', icon: '🔍', xpReward: 100, condition: 'first_sql' },
  { id: 'sql_expert', name: 'SQL Expert', description: 'Run 50 SQL queries', icon: '🧮', xpReward: 200, condition: 'sql_50' },
  { id: 'watchlist_starter', name: 'Watchlist Starter', description: 'Add your first item to watchlist', icon: '👁️', xpReward: 50, condition: 'first_watchlist' },
  { id: 'streak_3', name: 'Dedicated', description: 'Maintain a 3-day streak', icon: '🔥', xpReward: 150, condition: 'streak_3' },
  { id: 'streak_7', name: 'Committed', description: 'Maintain a 7-day streak', icon: '🔥', xpReward: 300, condition: 'streak_7' },
  { id: 'streak_30', name: 'Terminal Addict', description: 'Maintain a 30-day streak', icon: '💎', xpReward: 1000, condition: 'streak_30' },
  { id: 'panel_customizer', name: 'Panel Customizer', description: 'Add 5 custom panels', icon: '🎨', xpReward: 100, condition: 'add_panels_5' },
  { id: 'ml_trainer', name: 'ML Trainer', description: 'Train a machine learning model', icon: '🧠', xpReward: 200, condition: 'train_ml' },
  { id: 'prediction_maker', name: 'Crystal Ball', description: 'Make your first market prediction', icon: '🔮', xpReward: 100, condition: 'first_prediction' },
  { id: 'prediction_correct', name: 'Oracle', description: 'Get 5 predictions correct', icon: '✨', xpReward: 500, condition: 'correct_5' },
  { id: 'china_analyst', name: 'China Analyst', description: 'Explore all China panels', icon: '🐉', xpReward: 100, condition: 'all_china' },
  { id: 'defi_explorer', name: 'DeFi Explorer', description: 'Check DeFi TVL data', icon: '💰', xpReward: 75, condition: 'view_defi' },
  { id: 'night_owl', name: 'Night Owl', description: 'Use DragonScope after midnight', icon: '🦉', xpReward: 50, condition: 'night_use' },
  { id: 'early_bird', name: 'Early Bird', description: 'Use DragonScope before 6 AM', icon: '🌅', xpReward: 50, condition: 'early_use' },
  { id: 'chart_exporter', name: 'Chart Exporter', description: 'Export a chart as PNG', icon: '📊', xpReward: 75, condition: 'export_chart' },
  { id: 'theme_switcher', name: 'Theme Switcher', description: 'Switch between dark and light mode', icon: '🌓', xpReward: 25, condition: 'switch_theme' },
  { id: 'level_5', name: 'Rising Star', description: 'Reach level 5', icon: '⭐', xpReward: 500, condition: 'level_5' },
];
