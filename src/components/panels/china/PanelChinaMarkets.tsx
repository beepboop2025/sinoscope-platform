import { useState, useEffect, memo, type ReactElement } from 'react';
import { TrendingUp, TrendingDown, Activity, Globe } from 'lucide-react';
import { ChinaAPI } from '../../../services/api/chinaApi';
import { CHINA_INDICES, CHINA_BLUE_CHIPS } from '../../../constants/china';
import PanelChrome from '../../shared/PanelChrome';

interface IndexData { symbol: string; name: string; price?: number; change?: number; changesPercentage?: number; }
interface StockData { symbol: string; name: string; price?: number; change?: number; changesPercentage?: number; }
interface PanelChinaMarketsProps { apiKey?: string; }

const PanelChinaMarkets = memo(function PanelChinaMarkets({ apiKey }: PanelChinaMarketsProps): ReactElement {
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [stocks, setStocks] = useState<StockData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  useEffect(() => {
    let inFlight = false;
    async function fetchData() {
      if (inFlight) return;
      inFlight = true;
      setLoading(true);
      try {
        const [idxData, stockData] = await Promise.all([
          ChinaAPI.fetchChinaIndices(),
          ChinaAPI.fetchChinaStocks(),
        ]);
        setIndices(idxData as IndexData[]);
        setStocks(stockData as StockData[]);
        setLastUpdate(new Date().toLocaleTimeString());
      } catch (err) {
        console.warn('[PanelChinaMarkets]', (err as Error).message);
      } finally {
        setLoading(false);
        inFlight = false;
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [apiKey]);

  const formatChange = (change: number, pct: number): ReactElement => {
    const safeChange = Number(change) || 0;
    const safePct = Number(pct) || 0;
    const isPositive = safeChange >= 0;
    const Icon = isPositive ? TrendingUp : TrendingDown;
    const color = isPositive ? 'var(--green)' : 'var(--red)';
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color }}>
        <Icon size={14} /><span>{isPositive ? '+' : ''}{safeChange.toFixed(2)}</span>
        <span style={{ fontSize: 12, opacity: 0.8 }}>({isPositive ? '+' : ''}{safePct.toFixed(2)}%)</span>
      </div>
    );
  };

  if (loading) {
    return (
      <PanelChrome title="China Markets" icon={Globe} iconColor="var(--magenta)">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-2)' }}>
          <Activity size={16} className="spinner" /><span>Loading China markets...</span>
        </div>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="China Markets" icon={Globe} iconColor="var(--magenta)">
      <div style={{ padding: 4 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Updated: {lastUpdate}</span>
        </div>
        <div style={{ marginBottom: 20 }}>
          <h4 style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 12 }}>Major Indices</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            {indices.map((idx) => (
              <div key={idx.symbol} style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--divider)' }}>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>{idx.name}</div>
                <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 4 }}>{idx.price?.toFixed(2) || 'N/A'}</div>
                {formatChange(idx.change || 0, idx.changesPercentage || 0)}
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 12 }}>Major A-Shares</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {stocks.map((stock) => (
              <div key={stock.symbol} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--surface-1)', borderRadius: 6, border: '1px solid var(--divider)' }}>
                <div><div style={{ fontWeight: 500, fontSize: 13 }}>{stock.name}</div><div style={{ fontSize: 11, color: 'var(--text-3)' }}>{stock.symbol}</div></div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 600 }}>{stock.price?.toFixed(2)}</div>
                  <div style={{ fontSize: 11, color: (stock.change || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {(stock.change || 0) >= 0 ? '+' : ''}{(stock.changesPercentage || 0).toFixed(2)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PanelChrome>
  );
});
PanelChinaMarkets.displayName = 'PanelChinaMarkets';
export default PanelChinaMarkets;
