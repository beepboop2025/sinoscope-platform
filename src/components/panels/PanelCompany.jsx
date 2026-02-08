import { memo, useState, useEffect } from 'react';
import { Building } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchStockProfile } from '../../services/api/stockApi';
import { PanelSkeleton } from '../shared/LoadingSkeleton';
import { formatPrice } from '../../utils/formatters';

const PanelCompany = memo(({ symbol = 'AAPL' }) => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchStockProfile(symbol);
        if (data) setProfile(data);
      } catch (err) {
        console.warn('[PanelCompany]', err);
      }
      setLoading(false);
    }
    load();
  }, [symbol]);

  if (loading) return <PanelChrome title="Company Profile" icon={Building} iconColor="var(--blue)"><PanelSkeleton /></PanelChrome>;

  if (!profile) {
    return (
      <PanelChrome title="Company Profile" icon={Building} iconColor="var(--blue)">
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
          No profile data. Set VITE_FMP_API_KEY for company data.
        </div>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title={`${profile.companyName || symbol}`} icon={Building} iconColor="var(--blue)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase' }}>Market Cap</div>
            <div className="mono" style={{ fontSize: 14, fontWeight: 600 }}>${formatPrice(profile.mktCap)}</div>
          </div>
          <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase' }}>Sector</div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-1)' }}>{profile.sector || 'N/A'}</div>
          </div>
        </div>
        {profile.description && (
          <div style={{ fontSize: 11, color: 'var(--text-3)', lineHeight: 1.5, maxHeight: 80, overflow: 'hidden' }}>
            {profile.description.slice(0, 200)}...
          </div>
        )}
      </div>
    </PanelChrome>
  );
});
PanelCompany.displayName = "PanelCompany";
export default PanelCompany;
