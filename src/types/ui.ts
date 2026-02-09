import type { ReactNode } from 'react';

export interface PanelChromeProps {
  title: string;
  icon?: ReactNode;
  iconColor?: string;
  children: ReactNode;
  onClose?: () => void;
  lastUpdate?: number | null;
  defaultCollapsed?: boolean;
}

export interface DataTableColumn<T = Record<string, unknown>> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (value: unknown, row: T) => ReactNode;
  align?: 'left' | 'center' | 'right';
  width?: string;
}

export interface DataTableProps<T = Record<string, unknown>> {
  columns: DataTableColumn<T>[];
  data: T[];
  pageSize?: number;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  stickyHeader?: boolean;
  compact?: boolean;
}

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

export interface ToastContextValue {
  addToast: (type: ToastType, message: string, duration?: number) => void;
  removeToast: (id: string) => void;
}

export interface ThemeContextValue {
  isDark: boolean;
  toggle: () => void;
}

export interface AlertConfig {
  id: string;
  symbol: string;
  condition: 'price_above' | 'price_below' | 'pct_change_above' | 'pct_change_below';
  threshold: number;
  isActive: boolean;
  createdAt: number;
}

export interface TriggeredAlert {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  symbol: string;
  message: string;
  timestamp: number;
  configId?: string;
}
