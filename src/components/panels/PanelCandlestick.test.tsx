import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({
      setData: vi.fn(),
      applyOptions: vi.fn(),
      priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    })),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
      applyOptions: vi.fn(),
    })),
    resize: vi.fn(),
    remove: vi.fn(),
  })),
  CandlestickSeries: 'CandlestickSeries',
  HistogramSeries: 'HistogramSeries',
}));

// Mock the data hook
vi.mock('../../hooks/useCandlestickData', () => ({
  useCandlestickData: vi.fn(() => ({
    data: null,
    loading: true,
    error: null,
    refetch: vi.fn(),
  })),
  TIMEFRAMES: ['1D', '1W', '1M'],
}));

import PanelCandlestick from './PanelCandlestick';

describe('PanelCandlestick', () => {
  it('renders without crashing', () => {
    const { container } = render(<PanelCandlestick />);
    expect(container).toBeTruthy();
  });

  it('shows the panel title with default symbol', () => {
    render(<PanelCandlestick />);
    expect(screen.getByText('AAPL Candlestick')).toBeInTheDocument();
  });
});
