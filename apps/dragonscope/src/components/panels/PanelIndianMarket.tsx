import { memo, useState, useEffect, type ReactElement } from 'react';
import { TrendingUp, TrendingDown, Globe } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MarketIndex {
  name: string;
  value: number;
  change: number;
  changePct: number;
}

interface IndianMarketData {
  indices: MarketIndex[];
  inrUsd: { rate: number; change: number };
  rbiRepoRate: number;
  gsec10y: number;
  nseOpen: boolean;
  lastUpdated: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Check if NSE is currently open (Mon-Fri, 9:15 - 15:30 IST) */
function isNseOpen(): boolean {
  const now = new Date();
  // Convert to IST (UTC+5:30)
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60_000;
  const ist = new Date(utcMs + 5.5 * 3600_000);
  const day = ist.getDay();
  if (day === 0 || day === 6) return false; // Weekend
  const hours = ist.getHours();
  const mins = ist.getMinutes();
  const timeInMins = hours * 60 + mins;
  return timeInMins >= 555 && timeInMins <= 930; // 9:15 to 15:30
}

function generateMockData(): IndianMarketData {
  const niftyBase = 22_450;
  const sensexBase = 73_800;
  const niftyChange = +(Math.random() * 400 - 200).toFixed(2);
  const sensexChange = +(niftyChange * 3.3 + (Math.random() - 0.5) * 50).toFixed(2);
  const niftyBankBase = 47_200;
  const niftyBankChange = +(Math.random() * 600 - 300).toFixed(2);
  const niftyITBase = 33_100;
  const niftyITChange = +(Math.random() * 300 - 150).toFixed(2);

  return {
    indices: [
      { name: 'NIFTY 50', value: +(niftyBase + niftyChange).toFixed(2), change: niftyChange, changePct: +((niftyChange / niftyBase) * 100).toFixed(2) },
      { name: 'SENSEX', value: +(sensexBase + sensexChange).toFixed(2), change: sensexChange, changePct: +((sensexChange / sensexBase) * 100).toFixed(2) },
      { name: 'NIFTY BANK', value: +(niftyBankBase + niftyBankChange).toFixed(2), change: niftyBankChange, changePct: +((niftyBankChange / niftyBankBase) * 100).toFixed(2) },
      { name: 'NIFTY IT', value: +(niftyITBase + niftyITChange).toFixed(2), change: niftyITChange, changePct: +((niftyITChange / niftyITBase) * 100).toFixed(2) },
    ],
    inrUsd: {
      rate: +(83.1 + Math.random() * 0.8 - 0.4).toFixed(4),
      change: +(Math.random() * 0.3 - 0.15).toFixed(4),
    },
    rbiRepoRate: 6.5,
    gsec10y: +(7.05 + Math.random() * 0.15 - 0.075).toFixed(3),
    nseOpen: isNseOpen(),
    lastUpdated: Date.now(),
  };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ChangeDisplay({ change, changePct }: { change: number; changePct: number }): ReactElement {
  const positive = change >= 0;
  const color = positive ? 'var(--green)' : 'var(--red)';
  const Icon = positive ? TrendingUp : TrendingDown;
  const sign = positive ? '+' : '';

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color, fontFamily: 'var(--font-mono)', fontSize: 10 }}>
      <Icon size={9} />
      {sign}{change.toFixed(2)} ({sign}{changePct.toFixed(2)}%)
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PanelIndianMarket = memo((): ReactElement => {
  const [data, setData] = useState<IndianMarketData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      const mock = generateMockData();
      setData(mock);
      setLastUpdated(mock.lastUpdated);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  if (loading || !data) {
    return (
      <PanelChrome title="Indian Market" icon={Globe} iconColor="var(--amber)">
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  const inrPositive = data.inrUsd.change >= 0;

  return (
    <PanelChrome title="Indian Market" icon={Globe} iconColor="var(--amber)" lastUpdated={lastUpdated}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%', minHeight: 0 }}>
        {/* Market status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 4, borderBottom: '1px solid var(--border-1)' }}>
          <div style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: data.nseOpen ? 'var(--green)' : 'var(--red)',
            boxShadow: data.nseOpen ? '0 0 6px var(--green)' : 'none',
          }} />
          <span style={{ fontSize: 10, color: data.nseOpen ? 'var(--green)' : 'var(--text-4)', fontWeight: 600 }}>
            NSE: {data.nseOpen ? 'OPEN' : 'CLOSED'}
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-4)', marginLeft: 'auto' }}>IST hours: 9:15 - 15:30</span>
        </div>

        {/* Indices */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {data.indices.map((idx) => (
            <div key={idx.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 4px', borderBottom: '1px solid var(--border-1)' }}>
              <div>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-1)' }}>{idx.name}</div>
                <ChangeDisplay change={idx.change} changePct={idx.changePct} />
              </div>
              <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>
                {idx.value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
          ))}

          {/* Macro indicators */}
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>Macro Indicators</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
              {/* INR/USD */}
              <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-1)' }}>
                <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>INR/USD</div>
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-1)', marginTop: 2 }}>
                  {data.inrUsd.rate.toFixed(2)}
                </div>
                <div style={{ fontSize: 9, color: inrPositive ? 'var(--green)' : 'var(--red)', fontFamily: 'var(--font-mono)' }}>
                  {inrPositive ? '+' : ''}{data.inrUsd.change.toFixed(4)}
                </div>
              </div>

              {/* RBI Repo Rate */}
              <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-1)' }}>
                <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>RBI Repo</div>
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-1)', marginTop: 2 }}>
                  {data.rbiRepoRate.toFixed(2)}%
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-4)', fontFamily: 'var(--font-mono)' }}>unchanged</div>
              </div>

              {/* 10Y G-Sec */}
              <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-1)' }}>
                <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>10Y G-Sec</div>
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-1)', marginTop: 2 }}>
                  {data.gsec10y.toFixed(3)}%
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-4)', fontFamily: 'var(--font-mono)' }}>yield</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ fontSize: 9, color: 'var(--text-4)' }}>Mock data | BSE/NSE</div>
      </div>
    </PanelChrome>
  );
});
PanelIndianMarket.displayName = 'PanelIndianMarket';
export default PanelIndianMarket;
