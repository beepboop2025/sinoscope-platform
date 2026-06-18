import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock heavy dependencies
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({
      setData: vi.fn(),
      applyOptions: vi.fn(),
      priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    })),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn(), applyOptions: vi.fn() })),
    resize: vi.fn(),
    remove: vi.fn(),
  })),
  CandlestickSeries: 'CandlestickSeries',
  HistogramSeries: 'HistogramSeries',
  LineSeries: 'LineSeries',
  AreaSeries: 'AreaSeries',
}));

vi.mock('react-grid-layout', () => ({
  WidthProvider: (component: unknown) => component,
  Responsive: ({ children }: { children: unknown }) => children,
  ResponsiveGridLayout: ({ children }: { children: unknown }) => children,
  useContainerWidth: () => ({ containerRef: { current: null }, width: 1200, mounted: true }),
  default: ({ children }: { children: unknown }) => children,
}));

vi.mock('alasql', () => ({
  default: vi.fn(() => []),
}));

vi.mock('framer-motion', () => ({
  motion: new Proxy({}, {
    get: (_target, prop) => {
      if (typeof prop === 'string') {
        return ({ children, ...rest }: Record<string, unknown>) => {
          const { createElement } = require('react');
          return createElement(prop, rest, children);
        };
      }
    },
  }),
  AnimatePresence: ({ children }: { children: unknown }) => children,
  useReducedMotion: () => false,
}));

vi.mock('cmdk', () => ({
  Command: Object.assign(
    ({ children }: { children: unknown }) => children,
    {
      Input: () => null,
      List: ({ children }: { children: unknown }) => children,
      Empty: () => null,
      Group: ({ children }: { children: unknown }) => children,
      Item: ({ children }: { children: unknown }) => children,
      Dialog: ({ children }: { children: unknown }) => children,
    }
  ),
}));

vi.mock('sonner', () => ({
  toast: vi.fn(),
  Toaster: () => null,
}));

import App from './App';
import { ToastProvider } from './components/shared/Toast';
import { ThemeProvider } from './components/shared/ThemeProvider';
import { SymbolProvider } from './contexts/SymbolContext';

function TestWrapper({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <ThemeProvider>
        <SymbolProvider>
          {children}
        </SymbolProvider>
      </ThemeProvider>
    </ToastProvider>
  );
}

describe('App', () => {
  it('renders without crashing (smoke test)', () => {
    const { container } = render(
      <TestWrapper>
        <App />
      </TestWrapper>
    );
    expect(container).toBeTruthy();
    expect(container.firstChild).toBeTruthy();
  });
});
