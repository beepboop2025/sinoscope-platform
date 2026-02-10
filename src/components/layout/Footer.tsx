import { memo } from 'react';
import { getTokens } from '../../services/RateLimiter';
import { cacheStats } from '../../services/CacheManager';

interface FooterProps {
  lastUpdate: number | null | undefined;
  wsStatus: string;
}

const Footer = memo<FooterProps>(({ lastUpdate, wsStatus }) => {
  const stats = cacheStats();
  const freshness = lastUpdate ? `${Math.round((Date.now() - lastUpdate) / 1000)}s ago` : 'N/A';

  return (
    <div className="app-footer">
      <span>DragonScope v1.0</span>
      <span style={{ color: 'var(--border-3)' }}>|</span>
      <span>Data: {freshness}</span>
      <span style={{ color: 'var(--border-3)' }}>|</span>
      <span>Cache: {stats.active}/{stats.total}</span>
      <span style={{ color: 'var(--border-3)' }}>|</span>
      <span>
        API: Frankfurter({getTokens('frankfurter')}) CoinGecko({getTokens('coingecko')}) FRED({getTokens('fred')})
      </span>
      <span style={{ marginLeft: 'auto' }}>
        WS: <span style={{ color: wsStatus === 'connected' ? 'var(--green)' : 'var(--text-4)' }}>{wsStatus || 'off'}</span>
      </span>
    </div>
  );
});
Footer.displayName = "Footer";
export default Footer;
