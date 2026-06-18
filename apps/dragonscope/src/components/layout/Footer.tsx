import { memo, useState, useEffect, type ReactElement } from 'react';
import { HelpCircle, Monitor, Database, Wifi, WifiOff, ChevronUp, AlertCircle } from 'lucide-react';
import { getTokens } from '../../services/RateLimiter';
import { cacheStats } from '../../services/CacheManager';
import { getRecentErrorCount, onErrorCountChange } from '../../utils/errorReporter';

interface FreshnessInfo { label: string; color: string; level: string; }

function computeFreshness(lastUpdate: number | null | undefined): FreshnessInfo {
  if (!lastUpdate) return { label: 'No data', color: 'var(--text-4)', level: 'unknown' };
  const secs = Math.round((Date.now() - lastUpdate) / 1000);
  if (secs < 30) return { label: `${secs}s ago`, color: 'var(--green)', level: 'fresh' };
  if (secs < 120) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return { label: m > 0 ? `${m}m ${s}s ago` : `${secs}s ago`, color: 'var(--amber)', level: 'aging' };
  }
  return { label: `${Math.round(secs / 60)}m ago`, color: 'var(--red)', level: 'stale' };
}

interface FooterProps {
  lastUpdate: number | null | undefined;
  wsStatus: string;
  panelCount?: number;
  onShowShortcuts?: () => void;
}

const IS_DEV = import.meta.env.DEV;

const Footer = memo<FooterProps>(({ lastUpdate, wsStatus, panelCount = 0, onShowShortcuts }): ReactElement => {
  const stats = cacheStats();
  const freshness = computeFreshness(lastUpdate);

  // Re-compute freshness every 5s to keep the label current
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5000);
    return () => clearInterval(id);
  }, []);
  const [showApiDetail, setShowApiDetail] = useState(false);
  const [errorCount, setErrorCount] = useState(() => getRecentErrorCount());

  useEffect(() => {
    if (!IS_DEV) return;
    return onErrorCountChange(setErrorCount);
  }, []);

  const frankfurterTokens = getTokens('frankfurter');
  const coingeckoTokens = getTokens('coingecko');
  const fredTokens = getTokens('fred');
  const hitRatio = stats.total > 0 ? Math.round((stats.active / stats.total) * 100) : 0;

  const isConnected = wsStatus === 'connected' || wsStatus === 'live' || wsStatus === 'mock';

  return (
    <div className="app-footer">
      {/* Left section */}
      <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
        <Monitor size={10} color="var(--cyan)" />
        DragonScope v2.0
      </span>

      <span style={{ color: 'var(--border-3)' }}>|</span>

      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }} title={`Data freshness: ${freshness.level} — Last updated: ${freshness.label}`}>
        <Database size={10} color={freshness.color} />
        <span style={{ color: freshness.color, fontWeight: freshness.level === 'stale' ? 700 : 400 }}>
          {freshness.label}
        </span>
        {freshness.level === 'stale' && <span style={{ color: 'var(--red)', fontSize: 8 }}>STALE</span>}
      </span>

      <span style={{ color: 'var(--border-3)' }}>|</span>

      <span title={`${stats.active} active / ${stats.total} total entries (${hitRatio}% utilization)`}>
        Cache: {stats.active}/{stats.total} ({hitRatio}%)
      </span>

      <span style={{ color: 'var(--border-3)' }}>|</span>

      {panelCount > 0 && (
        <>
          <span title="Active panels">{panelCount} panels</span>
          <span style={{ color: 'var(--border-3)' }}>|</span>
        </>
      )}

      {/* API tokens with expandable detail */}
      <span style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 4 }}>
        <button
          onClick={() => setShowApiDetail(s => !s)}
          style={{
            background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 3, padding: 0, fontSize: 'inherit', fontFamily: 'inherit',
          }}
          title="API rate limit tokens (click for details)"
          aria-label="Toggle API rate limit details"
          aria-expanded={showApiDetail}
        >
          API
          <ChevronUp size={8} style={{ transform: showApiDetail ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }} />
        </button>
        {showApiDetail && (
          <div style={{
            position: 'absolute', bottom: '100%', left: 0, marginBottom: 8,
            background: 'var(--glass-bg-heavy)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
            border: '1px solid var(--border-2)', borderRadius: 'var(--radius-md)',
            padding: 10, minWidth: 180, zIndex: 100, boxShadow: 'var(--shadow-md)',
          }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', marginBottom: 8 }}>API Rate Limits</div>
            {[
              { name: 'Frankfurter', tokens: frankfurterTokens, max: 150 },
              { name: 'CoinGecko', tokens: coingeckoTokens, max: 50 },
              { name: 'FRED', tokens: fredTokens, max: 120 },
            ].map(api => (
              <div key={api.name} style={{ marginBottom: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--text-3)', marginBottom: 2 }}>
                  <span>{api.name}</span>
                  <span className="mono">{api.tokens}/{api.max}</span>
                </div>
                <div style={{ height: 3, background: 'var(--surface-2)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: `${Math.min((api.tokens / api.max) * 100, 100)}%`,
                    background: api.tokens > api.max * 0.3 ? 'var(--green)' : api.tokens > api.max * 0.1 ? 'var(--amber)' : 'var(--red)',
                    borderRadius: 2,
                    transition: 'width 0.3s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </span>

      {/* Dev-mode error counter */}
      {IS_DEV && errorCount > 0 && (
        <>
          <span style={{ color: 'var(--border-3)' }}>|</span>
          <span
            style={{ display: 'flex', alignItems: 'center', gap: 3, color: errorCount >= 5 ? 'var(--red)' : 'var(--amber)' }}
            title={`${errorCount} error${errorCount !== 1 ? 's' : ''} in the last 5 minutes`}
          >
            <AlertCircle size={10} aria-hidden="true" />
            {errorCount} err{errorCount !== 1 ? 's' : ''}/5min
          </span>
        </>
      )}

      {/* Right section */}
      <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
        {onShowShortcuts && (
          <button
            onClick={onShowShortcuts}
            style={{
              background: 'none', border: 'none', color: 'var(--text-4)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 3, padding: 0, fontSize: 'inherit', fontFamily: 'inherit',
            }}
            title="Keyboard shortcuts (Ctrl+?)"
            aria-label="Show keyboard shortcuts"
          >
            <HelpCircle size={11} aria-hidden="true" />
            <span>Help</span>
          </button>
        )}

        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {isConnected ? <Wifi size={10} color="var(--green)" /> : <WifiOff size={10} color="var(--text-4)" />}
          <span style={{ color: isConnected ? 'var(--green)' : 'var(--text-4)' }}>
            {wsStatus === 'mock' ? 'DEMO' : wsStatus || 'off'}
          </span>
        </span>
      </span>
    </div>
  );
});
Footer.displayName = "Footer";
export default Footer;
