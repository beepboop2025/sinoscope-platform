import { memo, useState, useEffect, useRef, useCallback, type ReactElement } from 'react';
import { BookOpen } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OrderBookEntry {
  price: number;
  quantity: number;
  cumulative: number;
}

interface OrderBookData {
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  spread: number;
  spreadPct: number;
  lastUpdated: number;
}

// ---------------------------------------------------------------------------
// Mock data generator
// ---------------------------------------------------------------------------

function generateOrderBook(midPrice: number): OrderBookData {
  const bids: OrderBookEntry[] = [];
  const asks: OrderBookEntry[] = [];
  let bidCum = 0;
  let askCum = 0;

  for (let i = 0; i < 12; i++) {
    const bidPrice = midPrice - (i + 1) * (midPrice * 0.0002) - Math.random() * midPrice * 0.0001;
    const bidQty = +(0.01 + Math.random() * 2.5).toFixed(4);
    bidCum += bidQty;
    bids.push({ price: +bidPrice.toFixed(2), quantity: bidQty, cumulative: +bidCum.toFixed(4) });
  }

  for (let i = 0; i < 12; i++) {
    const askPrice = midPrice + (i + 1) * (midPrice * 0.0002) + Math.random() * midPrice * 0.0001;
    const askQty = +(0.01 + Math.random() * 2.5).toFixed(4);
    askCum += askQty;
    asks.push({ price: +askPrice.toFixed(2), quantity: askQty, cumulative: +askCum.toFixed(4) });
  }

  const spread = asks[0].price - bids[0].price;
  const spreadPct = (spread / midPrice) * 100;

  return {
    bids,
    asks,
    spread: +spread.toFixed(2),
    spreadPct: +spreadPct.toFixed(4),
    lastUpdated: Date.now(),
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SYMBOL = 'BTC/USDT';
const MID_PRICE_BASE = 67_450;

const PanelOrderBook = memo((): ReactElement => {
  const [data, setData] = useState<OrderBookData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(() => {
    const midPrice = MID_PRICE_BASE + (Math.random() - 0.5) * 200;
    const book = generateOrderBook(midPrice);
    setData(book);
    setLastUpdated(book.lastUpdated);
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = setTimeout(loadData, 500);
    return () => clearTimeout(timer);
  }, [loadData]);

  // Live updates every 2 seconds
  useEffect(() => {
    intervalRef.current = setInterval(loadData, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [loadData]);

  if (loading || !data) {
    return (
      <PanelChrome title="Order Book" icon={BookOpen} iconColor="var(--blue)">
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  const maxBidCum = data.bids[data.bids.length - 1]?.cumulative || 1;
  const maxAskCum = data.asks[data.asks.length - 1]?.cumulative || 1;

  return (
    <PanelChrome title="Order Book" icon={BookOpen} iconColor="var(--blue)" lastUpdated={lastUpdated}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, height: '100%', minHeight: 0 }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>{SYMBOL}</span>
          <span style={{ fontSize: 9, color: 'var(--text-4)' }}>Live depth</span>
        </div>

        {/* Column headers */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 70px 70px', gap: 2, fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: 0.5, paddingBottom: 2 }}>
          <span>Depth</span>
          <span style={{ textAlign: 'right' }}>Qty</span>
          <span style={{ textAlign: 'right' }}>Price</span>
        </div>

        {/* Asks (reversed so lowest ask is closest to spread) */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', flexDirection: 'column-reverse' }}>
            {data.asks.map((entry, i) => {
              const depthPct = (entry.cumulative / maxAskCum) * 100;
              return (
                <div
                  key={`ask-${i}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 70px 70px',
                    gap: 2,
                    padding: '2px 4px',
                    position: 'relative',
                    fontSize: 10,
                  }}
                >
                  <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${depthPct}%`, background: 'rgba(239, 68, 68, 0.08)', borderRadius: 2, pointerEvents: 'none' }} />
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-4)', fontSize: 9 }}>
                    {entry.cumulative.toFixed(3)}
                  </span>
                  <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                    {entry.quantity.toFixed(4)}
                  </span>
                  <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--red)', fontWeight: 600 }}>
                    {entry.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Spread indicator */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 8,
            padding: '5px 0',
            borderTop: '1px solid var(--border-1)',
            borderBottom: '1px solid var(--border-1)',
            margin: '2px 0',
          }}>
            <span style={{ fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>
              ${((data.bids[0].price + data.asks[0].price) / 2).toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
            <span style={{ fontSize: 8, color: 'var(--text-4)', fontFamily: 'var(--font-mono)' }}>
              Spread: ${data.spread.toFixed(2)} ({data.spreadPct.toFixed(3)}%)
            </span>
          </div>

          {/* Bids */}
          <div>
            {data.bids.map((entry, i) => {
              const depthPct = (entry.cumulative / maxBidCum) * 100;
              return (
                <div
                  key={`bid-${i}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 70px 70px',
                    gap: 2,
                    padding: '2px 4px',
                    position: 'relative',
                    fontSize: 10,
                  }}
                >
                  <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${depthPct}%`, background: 'rgba(34, 197, 94, 0.08)', borderRadius: 2, pointerEvents: 'none' }} />
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-4)', fontSize: 9 }}>
                    {entry.cumulative.toFixed(3)}
                  </span>
                  <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
                    {entry.quantity.toFixed(4)}
                  </span>
                  <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--green)', fontWeight: 600 }}>
                    {entry.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div style={{ fontSize: 9, color: 'var(--text-4)', display: 'flex', justifyContent: 'space-between' }}>
          <span>Updates every 2s</span>
          <span>Mock data</span>
        </div>
      </div>
    </PanelChrome>
  );
});
PanelOrderBook.displayName = 'PanelOrderBook';
export default PanelOrderBook;
