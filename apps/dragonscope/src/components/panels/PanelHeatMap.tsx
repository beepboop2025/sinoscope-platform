import { memo, useState, useEffect, useRef, useCallback, type ReactElement } from 'react';
import { LayoutGrid } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HeatMapItem {
  symbol: string;
  name: string;
  sector: string;
  marketCap: number;
  change: number;
}

interface TreeNode {
  symbol: string;
  name: string;
  change: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const SECTORS: Record<string, Array<{ symbol: string; name: string; mcap: number }>> = {
  Technology: [
    { symbol: 'AAPL', name: 'Apple', mcap: 3200 },
    { symbol: 'MSFT', name: 'Microsoft', mcap: 3100 },
    { symbol: 'GOOGL', name: 'Alphabet', mcap: 2100 },
    { symbol: 'NVDA', name: 'NVIDIA', mcap: 1800 },
    { symbol: 'META', name: 'Meta', mcap: 1400 },
    { symbol: 'AVGO', name: 'Broadcom', mcap: 800 },
  ],
  'Consumer Cyclical': [
    { symbol: 'AMZN', name: 'Amazon', mcap: 2000 },
    { symbol: 'TSLA', name: 'Tesla', mcap: 800 },
    { symbol: 'HD', name: 'Home Depot', mcap: 380 },
  ],
  'Financial Services': [
    { symbol: 'BRK.B', name: 'Berkshire', mcap: 900 },
    { symbol: 'JPM', name: 'JPMorgan', mcap: 600 },
    { symbol: 'V', name: 'Visa', mcap: 550 },
    { symbol: 'MA', name: 'Mastercard', mcap: 420 },
  ],
  Healthcare: [
    { symbol: 'UNH', name: 'UnitedHealth', mcap: 520 },
    { symbol: 'JNJ', name: 'J&J', mcap: 400 },
    { symbol: 'LLY', name: 'Eli Lilly', mcap: 750 },
    { symbol: 'PFE', name: 'Pfizer', mcap: 160 },
  ],
  Energy: [
    { symbol: 'XOM', name: 'ExxonMobil', mcap: 500 },
    { symbol: 'CVX', name: 'Chevron', mcap: 300 },
  ],
};

function generateMockData(): HeatMapItem[] {
  const items: HeatMapItem[] = [];
  for (const [sector, stocks] of Object.entries(SECTORS)) {
    for (const s of stocks) {
      items.push({
        symbol: s.symbol,
        name: s.name,
        sector,
        marketCap: s.mcap,
        change: +(Math.random() * 8 - 4).toFixed(2),
      });
    }
  }
  return items;
}

// ---------------------------------------------------------------------------
// Simple treemap layout (squarified)
// ---------------------------------------------------------------------------

function layoutTreemap(items: HeatMapItem[], width: number, height: number): TreeNode[] {
  if (items.length === 0 || width <= 0 || height <= 0) return [];

  const total = items.reduce((s, i) => s + Math.max(i.marketCap, 1), 0);
  const sorted = [...items].sort((a, b) => b.marketCap - a.marketCap);
  const nodes: TreeNode[] = [];

  let x = 0, y = 0, remainW = width, remainH = height, remaining = total;

  let i = 0;
  while (i < sorted.length) {
    const isHorizontal = remainW >= remainH;
    const strip: typeof sorted = [];
    const side = isHorizontal ? remainH : remainW;
    let stripTotal = 0;
    let bestRatio = Infinity;

    // Build strip
    while (i < sorted.length) {
      const candidate = sorted[i];
      const testTotal = stripTotal + candidate.marketCap;
      const testArea = (testTotal / remaining) * remainW * remainH;
      const testSide = testArea / side;
      const worst = Math.max(...strip.map(s => {
        const a = (s.marketCap / testTotal) * testArea;
        const w = a / testSide;
        return Math.max(testSide / w, w / testSide);
      }), (() => {
        const a = (candidate.marketCap / testTotal) * testArea;
        const w = a / testSide;
        return Math.max(testSide / w, w / testSide);
      })());

      if (strip.length > 0 && worst > bestRatio) break;

      strip.push(candidate);
      stripTotal += candidate.marketCap;
      bestRatio = worst;
      i++;
    }

    // Place strip
    const stripFraction = stripTotal / remaining;
    const stripSize = isHorizontal ? remainW * stripFraction : remainH * stripFraction;
    let offset = 0;

    for (const item of strip) {
      const fraction = item.marketCap / stripTotal;
      const itemSize = side * fraction;

      if (isHorizontal) {
        nodes.push({ symbol: item.symbol, name: item.name, change: item.change, x, y: y + offset, w: stripSize, h: itemSize });
      } else {
        nodes.push({ symbol: item.symbol, name: item.name, change: item.change, x: x + offset, y, w: itemSize, h: stripSize });
      }
      offset += itemSize;
    }

    if (isHorizontal) {
      x += stripSize;
      remainW -= stripSize;
    } else {
      y += stripSize;
      remainH -= stripSize;
    }
    remaining -= stripTotal;
  }

  return nodes;
}

// ---------------------------------------------------------------------------
// Color helper
// ---------------------------------------------------------------------------

function changeColor(change: number): string {
  const clamped = Math.max(-5, Math.min(5, change));
  if (clamped > 0) {
    const intensity = Math.min(clamped / 5, 1);
    return `rgba(0, 220, 130, ${0.15 + intensity * 0.55})`;
  }
  if (clamped < 0) {
    const intensity = Math.min(-clamped / 5, 1);
    return `rgba(255, 68, 88, ${0.15 + intensity * 0.55})`;
  }
  return 'rgba(255,255,255,0.06)';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function PanelHeatMap(): ReactElement {
  const [items, setItems] = useState<HeatMapItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const timer = setTimeout(() => {
      setItems(generateMockData());
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      const entry = entries[0];
      if (entry) {
        setDims({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const nodes = layoutTreemap(items, dims.w, dims.h);

  if (loading) {
    return (
      <PanelChrome title="Market Heat Map" icon={LayoutGrid}>
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="Market Heat Map" icon={LayoutGrid} subtitle={`${items.length} stocks`}>
      <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
        {nodes.map(node => {
          const isSmall = node.w < 60 || node.h < 35;
          const isTiny = node.w < 40 || node.h < 25;
          return (
            <div
              key={node.symbol}
              onMouseEnter={() => setHovered(node.symbol)}
              onMouseLeave={() => setHovered(null)}
              style={{
                position: 'absolute',
                left: node.x, top: node.y, width: node.w - 1, height: node.h - 1,
                background: changeColor(node.change),
                border: hovered === node.symbol ? '1px solid rgba(255,255,255,0.3)' : '1px solid rgba(0,0,0,0.3)',
                borderRadius: 2,
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer', overflow: 'hidden', transition: 'border 0.15s',
              }}
            >
              {!isTiny && (
                <>
                  <span style={{ fontSize: isSmall ? 9 : 11, fontWeight: 700, color: '#fff', textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}>
                    {node.symbol}
                  </span>
                  {!isSmall && (
                    <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.8)', fontFamily: 'var(--font-mono)' }}>
                      {node.change > 0 ? '+' : ''}{node.change}%
                    </span>
                  )}
                </>
              )}
            </div>
          );
        })}

        {/* Tooltip */}
        {hovered && (() => {
          const node = nodes.find(n => n.symbol === hovered);
          const item = items.find(i => i.symbol === hovered);
          if (!node || !item) return null;
          return (
            <div style={{
              position: 'absolute', left: Math.min(node.x + node.w / 2, dims.w - 120), top: Math.max(node.y - 40, 0),
              background: 'rgba(10,10,20,0.95)', border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: 6, padding: '4px 8px', pointerEvents: 'none', zIndex: 10,
              fontSize: 10, color: 'var(--text-1)', whiteSpace: 'nowrap',
            }}>
              <div style={{ fontWeight: 600 }}>{item.symbol} - {item.name}</div>
              <div style={{ color: 'var(--text-3)' }}>{item.sector}</div>
              <div style={{ color: item.change > 0 ? 'var(--green)' : item.change < 0 ? 'var(--red)' : 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                {item.change > 0 ? '+' : ''}{item.change}%
              </div>
            </div>
          );
        })()}
      </div>
    </PanelChrome>
  );
}

export default memo(PanelHeatMap);
