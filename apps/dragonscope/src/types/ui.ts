import type { ReactNode, CSSProperties } from 'react';
import type { LucideIcon } from 'lucide-react';

export interface PanelChromeProps {
  title: string;
  icon?: LucideIcon;
  iconColor?: string;
  children: ReactNode;
  onClose?: () => void;
  className?: string;
  exportable?: boolean;
  lastUpdated?: number | null;
}

export interface DataTableColumn<T = Record<string, unknown>> {
  key: string;
  label: string;
  style?: CSSProperties;
  cellStyle?: CSSProperties;
  render?: (value: unknown, row: T) => ReactNode;
}

export interface DataTableProps<T = Record<string, unknown>> {
  columns: DataTableColumn<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
}

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: number;
  type: ToastType;
  message: string;
  duration: number;
}

export interface ToastContextValue {
  addToast: (message: string, type?: ToastType, duration?: number) => number;
}

export type Theme = 'light' | 'dark';

export interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
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
