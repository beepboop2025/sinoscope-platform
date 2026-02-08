/**
 * PanelTradeFlow - US-China Trade Balance Visualization
 * Shows trade flows, exports/imports, and trade war metrics
 */
import { useState, useEffect, useMemo } from 'react';
import { ArrowRightLeft, TrendingUp, TrendingDown, Package, Ship, Scale } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell, ReferenceLine } from 'recharts';
import { TRADE_CATEGORIES } from '../../../constants/china';

// Mock trade data (monthly US-China trade in billions USD)
const TRADE_DATA = [
  { month: 'Jan 24', exports: 42.3, imports: 36.8, balance: 5.5 },
  { month: 'Feb 24', exports: 38.1, imports: 32.4, balance: 5.7 },
  { month: 'Mar 24', exports: 44.5, imports: 38.2, balance: 6.3 },
  { month: 'Apr 24', exports: 41.2, imports: 35.6, balance: 5.6 },
  { month: 'May 24', exports: 45.8, imports: 39.1, balance: 6.7 },
  { month: 'Jun 24', exports: 43.6, imports: 37.4, balance: 6.2 },
  { month: 'Jul 24', exports: 46.2, imports: 40.3, balance: 5.9 },
  { month: 'Aug 24', exports: 44.9, imports: 38.7, balance: 6.2 },
  { month: 'Sep 24', exports: 47.3, imports: 41.5, balance: 5.8 },
  { month: 'Oct 24', exports: 48.1, imports: 42.8, balance: 5.3 },
  { month: 'Nov 24', exports: 46.5, imports: 40.2, balance: 6.3 },
  { month: 'Dec 24', exports: 49.2, imports: 43.6, balance: 5.6 },
];

// Annual trade deficit history
const DEFICIT_HISTORY = [
  { year: '2019', deficit: 345.2, tariff: 'Phase 1 talks' },
  { year: '2020', deficit: 310.8, tariff: 'Phase 1 deal' },
  { year: '2021', deficit: 355.3, tariff: 'Supply chain issues' },
  { year: '2022', deficit: 382.9, tariff: 'Post-COVID surge' },
  { year: '2023', deficit: 279.1, tariff: 'Trade normalization' },
  { year: '2024', deficit: 295.4, tariff: 'Current' },
];

export default function PanelTradeFlow() {
  const [selectedView, setSelectedView] = useState('monthly'); // 'monthly' | 'categories'

  const latestMonth = TRADE_DATA[TRADE_DATA.length - 1];
  const ytdExports = TRADE_DATA.reduce((sum, d) => sum + d.exports, 0);
  const ytdImports = TRADE_DATA.reduce((sum, d) => sum + d.imports, 0);
  const ytdBalance = ytdExports - ytdImports;

  const formatBillion = (val) => `$${val.toFixed(1)}B`;

  return (
    <div className="panel-content" style={{ padding: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ArrowRightLeft size={18} color="var(--green)" />
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>US-China Trade Flow</h3>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={() => setSelectedView('monthly')}
            style={{
              padding: '4px 10px',
              fontSize: 11,
              borderRadius: 4,
              border: 'none',
              background: selectedView === 'monthly' ? 'var(--primary)' : 'var(--surface-2)',
              color: selectedView === 'monthly' ? 'white' : 'var(--text-2)',
              cursor: 'pointer',
            }}
          >
            Monthly
          </button>
          <button
            onClick={() => setSelectedView('categories')}
            style={{
              padding: '4px 10px',
              fontSize: 11,
              borderRadius: 4,
              border: 'none',
              background: selectedView === 'categories' ? 'var(--primary)' : 'var(--surface-2)',
              color: selectedView === 'categories' ? 'white' : 'var(--text-2)',
              cursor: 'pointer',
            }}
          >
            Categories
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--divider)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Ship size={12} color="var(--green)" />
            <span style={{ fontSize: 10, color: 'var(--text-3)' }}>US Exports to China</span>
          </div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{formatBillion(latestMonth.exports)}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Monthly</div>
        </div>

        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--divider)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Package size={12} color="var(--red)" />
            <span style={{ fontSize: 10, color: 'var(--text-3)' }}>US Imports from China</span>
          </div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{formatBillion(latestMonth.imports)}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Monthly</div>
        </div>

        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--divider)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Scale size={12} color={ytdBalance >= 0 ? 'var(--green)' : 'var(--red)'} />
            <span style={{ fontSize: 10, color: 'var(--text-3)' }}>Trade Balance</span>
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, color: ytdBalance >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {ytdBalance >= 0 ? '+' : ''}{formatBillion(ytdBalance)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>YTD 2024</div>
        </div>
      </div>

      {/* Monthly Trade Chart */}
      {selectedView === 'monthly' && (
        <>
          <div style={{ height: 180, marginBottom: 16 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={TRADE_DATA} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <XAxis dataKey="month" tick={{ fontSize: 9 }} interval={2} />
                <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  formatter={(value) => formatBillion(value)}
                  contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--divider)', fontSize: 11 }}
                />
                <ReferenceLine y={0} stroke="var(--divider)" />
                <Bar dataKey="exports" name="US Exports" fill="var(--green)" opacity={0.8} radius={[2, 2, 0, 0]} />
                <Bar dataKey="imports" name="US Imports" fill="var(--red)" opacity={0.8} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Trade Deficit History */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-2)', marginBottom: 8 }}>
              Annual Trade Deficit History
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {DEFICIT_HISTORY.map((item) => (
                <div
                  key={item.year}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '8px 10px',
                    background: 'var(--surface-1)',
                    borderRadius: 6,
                  }}
                >
                  <div style={{ minWidth: 40, fontSize: 11, fontWeight: 500 }}>{item.year}</div>
                  <div style={{ flex: 1, height: 8, background: 'var(--surface-3)', borderRadius: 4, overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${(item.deficit / 400) * 100}%`,
                        height: '100%',
                        background: 'var(--red)',
                        opacity: 0.7,
                      }}
                    />
                  </div>
                  <div style={{ minWidth: 60, fontSize: 11, textAlign: 'right' }}>
                    ${item.deficit.toFixed(0)}B
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-3)', minWidth: 100, textAlign: 'right' }}>
                    {item.tariff}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Categories View */}
      {selectedView === 'categories' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Top Exports */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
              <TrendingUp size={12} color="var(--green)" />
              <span style={{ fontSize: 11, fontWeight: 500 }}>Top US Exports to China</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {TRADE_CATEGORIES.exports.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ minWidth: 80, fontSize: 11 }}>{item.category}</div>
                  <div style={{ flex: 1, height: 6, background: 'var(--surface-3)', borderRadius: 3 }}>
                    <div
                      style={{
                        width: `${item.share}%`,
                        height: '100%',
                        background: 'var(--green)',
                        opacity: 0.7,
                        borderRadius: 3,
                      }}
                    />
                  </div>
                  <div style={{ minWidth: 30, fontSize: 10, color: 'var(--text-3)' }}>{item.share}%</div>
                </div>
              ))}
            </div>
          </div>

          {/* Top Imports */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
              <TrendingDown size={12} color="var(--red)" />
              <span style={{ fontSize: 11, fontWeight: 500 }}>Top US Imports from China</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {TRADE_CATEGORIES.imports.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ minWidth: 80, fontSize: 11 }}>{item.category}</div>
                  <div style={{ flex: 1, height: 6, background: 'var(--surface-3)', borderRadius: 3 }}>
                    <div
                      style={{
                        width: `${item.share}%`,
                        height: '100%',
                        background: 'var(--red)',
                        opacity: 0.7,
                        borderRadius: 3,
                      }}
                    />
                  </div>
                  <div style={{ minWidth: 30, fontSize: 10, color: 'var(--text-3)' }}>{item.share}%</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tariff Note */}
      <div
        style={{
          marginTop: 16,
          padding: 10,
          background: 'var(--amber-alpha)',
          borderRadius: 6,
          border: '1px solid var(--amber)',
          fontSize: 10,
          color: 'var(--text-2)',
        }}
      >
        <strong>Note:</strong> Average US tariffs on Chinese goods remain at ~19% (down from peak of 21%). 
        China maintains retaliatory tariffs on ~$110B of US goods. Phase 1 purchase commitments expired in 2021.
      </div>
    </div>
  );
}
