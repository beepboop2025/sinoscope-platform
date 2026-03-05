import { useState, useRef, useEffect, type ReactElement } from 'react';
import { ArrowRightLeft, TrendingUp, TrendingDown, Package, Ship, Scale, Info } from 'lucide-react';
import { createChart, HistogramSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import { TRADE_CATEGORIES } from '../../../constants/china';
import PanelChrome from '../../shared/PanelChrome';

interface TradeMonth { month: string; exports: number; imports: number; balance: number; }
interface DeficitYear { year: string; deficit: number; tariff: string; }
interface CategoryItem { category: string; share: number; }

const TRADE_DATA_LAST_UPDATED = '2024-12';
const TRADE_DATA: TradeMonth[] = [
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

const DEFICIT_HISTORY: DeficitYear[] = [
  { year: '2019', deficit: 345.2, tariff: 'Phase 1 talks' },
  { year: '2020', deficit: 310.8, tariff: 'Phase 1 deal' },
  { year: '2021', deficit: 355.3, tariff: 'Supply chain issues' },
  { year: '2022', deficit: 382.9, tariff: 'Post-COVID surge' },
  { year: '2023', deficit: 279.1, tariff: 'Trade normalization' },
  { year: '2024', deficit: 295.4, tariff: 'Current' },
];

function getCSSVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export default function PanelTradeFlow(): ReactElement {
  const [selectedView, setSelectedView] = useState<string>('monthly');
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const exportSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const importSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const latestMonth = TRADE_DATA[TRADE_DATA.length - 1];
  const ytdExports = TRADE_DATA.reduce((sum, d) => sum + d.exports, 0);
  const ytdImports = TRADE_DATA.reduce((sum, d) => sum + d.imports, 0);
  const ytdBalance = ytdExports - ytdImports;

  const formatBillion = (val: number): string => `$${val.toFixed(1)}B`;
  const tradeCategories = TRADE_CATEGORIES as unknown as { exports: CategoryItem[]; imports: CategoryItem[] };

  // Create chart
  useEffect(() => {
    if (selectedView !== 'monthly') return;
    const container = chartContainerRef.current;
    if (!container) return;

    const bg = getCSSVar('--bg-1') || '#0a0f1a';
    const text = getCSSVar('--text-3') || '#64748b';
    const border = getCSSVar('--border-1') || 'rgba(255,255,255,0.06)';
    const green = getCSSVar('--green') || '#00DC82';
    const red = getCSSVar('--red') || '#FF4458';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 180,
      layout: { background: { color: bg }, textColor: text, fontFamily: 'JetBrains Mono, monospace', fontSize: 9 },
      grid: { vertLines: { color: border }, horzLines: { color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border },
    });

    const exportSeries = chart.addSeries(HistogramSeries, { color: green + 'CC' });
    const importSeries = chart.addSeries(HistogramSeries, { color: red + 'CC', priceScaleId: '' });
    importSeries.priceScale().applyOptions({ scaleMargins: { top: 0.5, bottom: 0 } });

    chartRef.current = chart;
    exportSeriesRef.current = exportSeries;
    importSeriesRef.current = importSeries;

    // Set data
    const exportData = TRADE_DATA.map((d, i) => ({ time: i as UTCTimestamp, value: d.exports }));
    const importData = TRADE_DATA.map((d, i) => ({ time: i as UTCTimestamp, value: -d.imports }));
    exportSeries.setData(exportData);
    importSeries.setData(importData);
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (container.clientWidth > 0) {
        chart.applyOptions({ width: container.clientWidth });
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      exportSeriesRef.current = null;
      importSeriesRef.current = null;
    };
  }, [selectedView]);

  return (
    <PanelChrome title="US-China Trade Flow" icon={ArrowRightLeft} iconColor="var(--green)">
      <div style={{ padding: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {['monthly', 'categories'].map(v => (
            <button key={v} onClick={() => setSelectedView(v)} style={{
              padding: '4px 10px', fontSize: 11, borderRadius: 4, border: 'none',
              background: selectedView === v ? 'var(--cyan)' : 'var(--surface-2)',
              color: selectedView === v ? 'white' : 'var(--text-2)', cursor: 'pointer', textTransform: 'capitalize',
            }}>{v === 'monthly' ? 'Monthly' : 'Categories'}</button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--border-1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}><Ship size={12} color="var(--green)" /><span style={{ fontSize: 10, color: 'var(--text-3)' }}>US Exports to China</span></div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{formatBillion(latestMonth.exports)}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Monthly</div>
        </div>
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--border-1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}><Package size={12} color="var(--red)" /><span style={{ fontSize: 10, color: 'var(--text-3)' }}>US Imports from China</span></div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{formatBillion(latestMonth.imports)}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Monthly</div>
        </div>
        <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--border-1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}><Scale size={12} color={ytdBalance >= 0 ? 'var(--green)' : 'var(--red)'} /><span style={{ fontSize: 10, color: 'var(--text-3)' }}>Trade Balance</span></div>
          <div style={{ fontSize: 18, fontWeight: 600, color: ytdBalance >= 0 ? 'var(--green)' : 'var(--red)' }}>{ytdBalance >= 0 ? '+' : ''}{formatBillion(ytdBalance)}</div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>YTD 2024</div>
        </div>
      </div>

      {selectedView === 'monthly' && (
        <>
          <div ref={chartContainerRef} style={{ height: 180, marginBottom: 16 }} />
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-2)', marginBottom: 8 }}>Annual Trade Deficit History</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {DEFICIT_HISTORY.map((item) => (
                <div key={item.year} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: 'var(--surface-1)', borderRadius: 6 }}>
                  <div style={{ minWidth: 40, fontSize: 11, fontWeight: 500 }}>{item.year}</div>
                  <div style={{ flex: 1, height: 8, background: 'var(--surface-3)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ width: `${(item.deficit / 400) * 100}%`, height: '100%', background: 'var(--red)', opacity: 0.7 }} />
                  </div>
                  <div style={{ minWidth: 60, fontSize: 11, textAlign: 'right' }}>${item.deficit.toFixed(0)}B</div>
                  <div style={{ fontSize: 9, color: 'var(--text-3)', minWidth: 100, textAlign: 'right' }}>{item.tariff}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {selectedView === 'categories' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}><TrendingUp size={12} color="var(--green)" /><span style={{ fontSize: 11, fontWeight: 500 }}>Top US Exports to China</span></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tradeCategories.exports.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ minWidth: 80, fontSize: 11 }}>{item.category}</div>
                  <div style={{ flex: 1, height: 6, background: 'var(--surface-3)', borderRadius: 3 }}><div style={{ width: `${item.share}%`, height: '100%', background: 'var(--green)', opacity: 0.7, borderRadius: 3 }} /></div>
                  <div style={{ minWidth: 30, fontSize: 10, color: 'var(--text-3)' }}>{item.share}%</div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}><TrendingDown size={12} color="var(--red)" /><span style={{ fontSize: 11, fontWeight: 500 }}>Top US Imports from China</span></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tradeCategories.imports.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ minWidth: 80, fontSize: 11 }}>{item.category}</div>
                  <div style={{ flex: 1, height: 6, background: 'var(--surface-3)', borderRadius: 3 }}><div style={{ width: `${item.share}%`, height: '100%', background: 'var(--red)', opacity: 0.7, borderRadius: 3 }} /></div>
                  <div style={{ minWidth: 30, fontSize: 10, color: 'var(--text-3)' }}>{item.share}%</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div style={{ marginTop: 16, padding: 10, background: 'var(--amber-alpha)', borderRadius: 6, border: '1px solid var(--amber)', fontSize: 10, color: 'var(--text-2)' }}>
        <strong>Note:</strong> Average US tariffs on Chinese goods remain at ~19% (down from peak of 21%). China maintains retaliatory tariffs on ~$110B of US goods. Phase 1 purchase commitments expired in 2021.
      </div>

      <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, fontSize: 9, color: 'var(--text-3)' }}>
        <Info size={9} /><span>Reference data as of {TRADE_DATA_LAST_UPDATED} — Source: US Census Bureau / BEA (illustrative)</span>
      </div>
    </div>
    </PanelChrome>
  );
}
