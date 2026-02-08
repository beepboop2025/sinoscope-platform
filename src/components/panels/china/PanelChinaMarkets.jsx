/**
 * PanelChinaMarkets - China Stock Markets Overview
 * Displays SSE, CSI 300, Hang Seng indices and major A-shares
 */
import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity, Globe } from 'lucide-react';
import { ChinaAPI } from '../../../services/api/chinaApi';
import { CHINA_INDICES, CHINA_BLUE_CHIPS } from '../../../constants/china';

export default function PanelChinaMarkets({ apiKey }) {
  const [indices, setIndices] = useState([]);
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      const [idxData, stockData] = await Promise.all([
        ChinaAPI.fetchChinaIndices(apiKey),
        ChinaAPI.fetchChinaStocks(apiKey),
      ]);
      setIndices(idxData);
      setStocks(stockData);
      setLastUpdate(new Date().toLocaleTimeString());
      setLoading(false);
    }

    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [apiKey]);

  const formatChange = (change, pct) => {
    const isPositive = change >= 0;
    const Icon = isPositive ? TrendingUp : TrendingDown;
    const color = isPositive ? 'var(--green)' : 'var(--red)';
    
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color }}>
        <Icon size={14} />
        <span>{isPositive ? '+' : ''}{change.toFixed(2)}</span>
        <span style={{ fontSize: 12, opacity: 0.8 }}>({isPositive ? '+' : ''}{pct.toFixed(2)}%)</span>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="panel-content" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-2)' }}>
          <Activity size={16} className="spinner" />
          <span>Loading China markets...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="panel-content" style={{ padding: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Globe size={18} color="var(--magenta)" />
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>China Markets</h3>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-3)' }}>
          Updated: {lastUpdate}
        </span>
      </div>

      {/* Major Indices */}
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 12 }}>
          Major Indices
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          {indices.map((idx) => (
            <div
              key={idx.symbol}
              style={{
                padding: 12,
                background: 'var(--surface-2)',
                borderRadius: 8,
                border: '1px solid var(--divider)',
              }}
            >
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>
                {idx.name}
              </div>
              <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 4 }}>
                {idx.price?.toFixed(2) || 'N/A'}
              </div>
              {formatChange(idx.change || 0, idx.changesPercentage || 0)}
            </div>
          ))}
        </div>
      </div>

      {/* Blue Chip Stocks */}
      <div>
        <h4 style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 12 }}>
          Major A-Shares
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {stocks.map((stock) => (
            <div
              key={stock.symbol}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 12px',
                background: 'var(--surface-1)',
                borderRadius: 6,
                border: '1px solid var(--divider)',
              }}
            >
              <div>
                <div style={{ fontWeight: 500, fontSize: 13 }}>{stock.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{stock.symbol}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 600 }}>{stock.price?.toFixed(2)}</div>
                <div
                  style={{
                    fontSize: 11,
                    color: (stock.change || 0) >= 0 ? 'var(--green)' : 'var(--red)',
                  }}
                >
                  {(stock.change || 0) >= 0 ? '+' : ''}
                  {(stock.changesPercentage || 0).toFixed(2)}%
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
