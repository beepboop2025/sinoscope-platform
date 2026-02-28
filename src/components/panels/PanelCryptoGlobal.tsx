import { memo, useState, useEffect, useCallback, type ReactElement } from 'react';
import { Globe2, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchCryptoGlobal, fetchTrendingCoins, getMockCryptoGlobal, getMockTrending } from '../../services/api/coinGeckoGlobalApi';

interface CryptoGlobalData { totalMarketCap?: number; totalVolume?: number; marketCapChange24h?: number; activeCryptos?: number; btcDominance?: number; ethDominance?: number; }
interface TrendingCoin { id: string; symbol: string; name: string; rank?: number; }

function fmt(n: number | undefined): string {
  const v = Number(n) || 0;
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T';
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
  return '$' + v.toLocaleString();
}

const PanelCryptoGlobal = memo((): ReactElement => {
  const [global, setGlobal] = useState<CryptoGlobalData | null>(null);
  const [trending, setTrending] = useState<TrendingCoin[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [g, t] = await Promise.all([fetchCryptoGlobal(), fetchTrendingCoins()]);
      setGlobal((g || getMockCryptoGlobal()) as CryptoGlobalData);
      setTrending((t || getMockTrending()) as TrendingCoin[]);
    } catch {
      setGlobal(getMockCryptoGlobal() as CryptoGlobalData);
      setTrending(getMockTrending() as TrendingCoin[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const g = global || {} as CryptoGlobalData;

  return (
    <PanelChrome title="Crypto Global" icon={Globe2} iconColor="var(--orange)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%', minHeight: 0 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
          <div style={{ background: 'var(--bg-1)', borderRadius: 4, padding: '6px 8px' }}>
            <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>Total Market Cap</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-1)', fontFamily: 'JetBrains Mono, monospace' }}>{fmt(g.totalMarketCap)}</div>
            <div style={{ fontSize: 9, color: (g.marketCapChange24h || 0) >= 0 ? 'var(--green)' : 'var(--red)', display: 'flex', alignItems: 'center', gap: 2 }}>
              {(g.marketCapChange24h || 0) >= 0 ? <TrendingUp size={9} /> : <TrendingDown size={9} />}{Math.abs(g.marketCapChange24h || 0).toFixed(2)}% 24h
            </div>
          </div>
          <div style={{ background: 'var(--bg-1)', borderRadius: 4, padding: '6px 8px' }}>
            <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>24h Volume</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-1)', fontFamily: 'JetBrains Mono, monospace' }}>{fmt(g.totalVolume)}</div>
            <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{(g.activeCryptos || 0).toLocaleString()} coins</div>
          </div>
        </div>
        <div style={{ padding: '0 2px' }}>
          <div style={{ fontSize: 9, color: 'var(--text-4)', marginBottom: 4 }}>Market Dominance</div>
          <div style={{ display: 'flex', height: 16, borderRadius: 4, overflow: 'hidden', gap: 1 }}>
            <div style={{ width: `${g.btcDominance || 50}%`, background: '#f7931a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: '#fff', fontWeight: 700 }}>BTC {(g.btcDominance || 0).toFixed(1)}%</div>
            <div style={{ width: `${g.ethDominance || 17}%`, background: '#627eea', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: '#fff', fontWeight: 700 }}>ETH {(g.ethDominance || 0).toFixed(1)}%</div>
            <div style={{ flex: 1, background: 'var(--bg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: 'var(--text-3)', fontWeight: 600 }}>Others</div>
          </div>
        </div>
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <div style={{ fontSize: 9, color: 'var(--text-4)', marginBottom: 4, fontWeight: 600 }}>Trending on CoinGecko</div>
          {trending.map((coin, i) => (
            <div key={coin.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 2px', borderBottom: '1px solid var(--border-1)', fontSize: 10 }}>
              <span style={{ color: 'var(--text-4)', width: 14, textAlign: 'right' }}>{i + 1}</span>
              <span style={{ fontWeight: 600, color: 'var(--orange)', fontFamily: 'JetBrains Mono, monospace' }}>{coin.symbol}</span>
              <span style={{ color: 'var(--text-3)', flex: 1 }}>{coin.name}</span>
              {coin.rank && <span className="badge" style={{ background: 'var(--bg-3)', color: 'var(--text-4)', fontSize: 8, padding: '1px 4px' }}>#{coin.rank}</span>}
            </div>
          ))}
        </div>
        <button className="btn-ghost" onClick={loadData} disabled={loading} style={{ alignSelf: 'flex-end', padding: '2px 8px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3 }}><RefreshCw size={9} /> Refresh</button>
      </div>
    </PanelChrome>
  );
});
PanelCryptoGlobal.displayName = 'PanelCryptoGlobal';
export default PanelCryptoGlobal;
