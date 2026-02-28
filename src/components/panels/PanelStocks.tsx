import { memo, type ReactElement } from 'react';
import { TrendingUp } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { priceChangeColor } from '../../constants/colors';
import { formatVolume } from '../../utils/formatters';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import type { MarketTick } from '../../types/market';

const SIGNAL_COLORS: Record<string, string> = {
  oversold: 'var(--green)', overbought: 'var(--red)',
  bullish_crossover: 'var(--green)', bearish_crossover: 'var(--red)',
  below_lower_band: 'var(--green)', above_upper_band: 'var(--red)',
};

const SIGNAL_LABELS: Record<string, string> = {
  oversold: 'Oversold', overbought: 'Overbought',
  bullish_crossover: 'MACD Bull', bearish_crossover: 'MACD Bear',
  below_lower_band: 'BB Low', above_upper_band: 'BB High',
};

interface PanelStocksProps {
  data?: Record<string, MarketTick>;
  signals?: Record<string, Array<{ type: string }>>;
}

const PanelStocks = memo(({ data, signals = {} }: PanelStocksProps): ReactElement => {
  if (!data || Object.keys(data).length === 0) {
    return <PanelChrome title="Stock Watchlist" icon={TrendingUp} iconColor="var(--blue)"><PanelSkeleton /></PanelChrome>;
  }

  const stocks = Object.entries(data);
  const hasSignals = Object.keys(signals).length > 0;

  return (
    <PanelChrome title="Stock Watchlist" icon={TrendingUp} iconColor="var(--blue)">
      <table className="dense-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th style={{ textAlign: 'right' }}>Price</th>
            <th style={{ textAlign: 'right' }}>Chg%</th>
            <th style={{ textAlign: 'right' }}>Volume</th>
            {hasSignals && <th style={{ textAlign: 'right' }}>Signal</th>}
          </tr>
        </thead>
        <tbody>
          {stocks.map(([sym, d]) => {
            const symSignals = signals[sym] || [];
            const topSignal = symSignals[0];
            return (
              <tr key={sym}>
                <td style={{ color: 'var(--text-1)', fontWeight: 500, fontFamily: 'Outfit' }}>{sym}</td>
                <td style={{ textAlign: 'right' }}>{(Number(d.price) || 0).toFixed(2)}</td>
                <td style={{ textAlign: 'right', color: priceChangeColor(d.changePct) }}>
                  {(Number(d.changePct) || 0) >= 0 ? '+' : ''}{(Number(d.changePct) || 0).toFixed(2)}%
                </td>
                <td style={{ textAlign: 'right', color: 'var(--text-3)' }}>{formatVolume(d.volume)}</td>
                {hasSignals && (
                  <td style={{ textAlign: 'right', fontSize: 8, color: topSignal ? (SIGNAL_COLORS[topSignal.type] || 'var(--text-3)') : 'var(--text-4)' }}>
                    {topSignal ? (SIGNAL_LABELS[topSignal.type] || topSignal.type) : '-'}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </PanelChrome>
  );
});
PanelStocks.displayName = "PanelStocks";
export default PanelStocks;
