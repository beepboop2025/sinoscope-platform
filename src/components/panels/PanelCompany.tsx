import { memo, useState, useEffect, useCallback, type ReactElement, type FormEvent, type ChangeEvent } from 'react';
import { Building, Search, ExternalLink } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { fetchStockProfile } from '../../services/api/stockApi';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

interface CompanyProfile {
  companyName?: string;
  symbol?: string;
  sector?: string;
  industry?: string;
  mktCap?: number;
  price?: number;
  beta?: number;
  ceo?: string;
  country?: string;
  exchange?: string;
  website?: string;
  description?: string;
}

const POPULAR = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM', 'V', 'WMT'];

const MOCK_PROFILES: Record<string, CompanyProfile> = {
  AAPL: { companyName: 'Apple Inc.', symbol: 'AAPL', sector: 'Technology', industry: 'Consumer Electronics', mktCap: 3420000000000, price: 228.5, beta: 1.24, ceo: 'Tim Cook', country: 'US', exchange: 'NASDAQ', website: 'https://apple.com', description: 'Apple designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories.' },
  MSFT: { companyName: 'Microsoft Corporation', symbol: 'MSFT', sector: 'Technology', industry: 'Software', mktCap: 3100000000000, price: 415.2, beta: 0.89, ceo: 'Satya Nadella', country: 'US', exchange: 'NASDAQ', website: 'https://microsoft.com', description: 'Microsoft develops and licenses software, services, devices, and solutions worldwide.' },
  GOOGL: { companyName: 'Alphabet Inc.', symbol: 'GOOGL', sector: 'Communication Services', industry: 'Internet', mktCap: 2100000000000, price: 176.3, beta: 1.06, ceo: 'Sundar Pichai', country: 'US', exchange: 'NASDAQ', website: 'https://abc.xyz', description: 'Alphabet provides online advertising services, cloud computing, and other technology products.' },
  AMZN: { companyName: 'Amazon.com Inc.', symbol: 'AMZN', sector: 'Consumer Cyclical', industry: 'E-Commerce', mktCap: 2000000000000, price: 192.7, beta: 1.16, ceo: 'Andy Jassy', country: 'US', exchange: 'NASDAQ', website: 'https://amazon.com', description: 'Amazon engages in e-commerce, cloud computing (AWS), digital streaming, and artificial intelligence.' },
  NVDA: { companyName: 'NVIDIA Corporation', symbol: 'NVDA', sector: 'Technology', industry: 'Semiconductors', mktCap: 2800000000000, price: 875.4, beta: 1.67, ceo: 'Jensen Huang', country: 'US', exchange: 'NASDAQ', website: 'https://nvidia.com', description: 'NVIDIA designs GPU-accelerated computing platforms for gaming, data centers, and AI applications.' },
  META: { companyName: 'Meta Platforms Inc.', symbol: 'META', sector: 'Communication Services', industry: 'Social Media', mktCap: 1300000000000, price: 510.8, beta: 1.22, ceo: 'Mark Zuckerberg', country: 'US', exchange: 'NASDAQ', website: 'https://meta.com', description: 'Meta builds technologies for connecting people through social networking, messaging, and virtual reality.' },
  TSLA: { companyName: 'Tesla Inc.', symbol: 'TSLA', sector: 'Consumer Cyclical', industry: 'Auto Manufacturers', mktCap: 780000000000, price: 245.6, beta: 2.07, ceo: 'Elon Musk', country: 'US', exchange: 'NASDAQ', website: 'https://tesla.com', description: 'Tesla designs, manufactures, and sells electric vehicles, energy generation, and storage systems.' },
  JPM: { companyName: 'JPMorgan Chase & Co.', symbol: 'JPM', sector: 'Financial Services', industry: 'Banking', mktCap: 590000000000, price: 205.3, beta: 1.09, ceo: 'Jamie Dimon', country: 'US', exchange: 'NYSE', website: 'https://jpmorganchase.com', description: 'JPMorgan Chase operates as a financial services company providing investment banking, asset management, and consumer banking.' },
  V: { companyName: 'Visa Inc.', symbol: 'V', sector: 'Financial Services', industry: 'Payment Processing', mktCap: 550000000000, price: 280.1, beta: 0.94, ceo: 'Ryan McInerney', country: 'US', exchange: 'NYSE', website: 'https://visa.com', description: 'Visa operates as a payments technology company facilitating digital payments worldwide.' },
  WMT: { companyName: 'Walmart Inc.', symbol: 'WMT', sector: 'Consumer Defensive', industry: 'Retail', mktCap: 530000000000, price: 168.4, beta: 0.52, ceo: 'Doug McMillon', country: 'US', exchange: 'NYSE', website: 'https://walmart.com', description: 'Walmart operates retail stores, warehouse clubs, and e-commerce websites worldwide.' },
};

function formatMktCap(val: number | undefined): string {
  const n = Number(val) || 0;
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

interface PanelCompanyProps {
  symbol?: string;
}

const PanelCompany = memo(({ symbol: propSymbol = 'AAPL' }: PanelCompanyProps): ReactElement => {
  const [symbol, setSymbol] = useState<string>(propSymbol);
  const [input, setInput] = useState<string>('');
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadProfile = useCallback(async (sym: string) => {
    setLoading(true);
    try {
      const data = await fetchStockProfile(sym);
      if (data) {
        setProfile(data as CompanyProfile);
      } else {
        setProfile(MOCK_PROFILES[sym] || null);
      }
    } catch {
      setProfile(MOCK_PROFILES[sym] || null);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadProfile(symbol); }, [symbol, loadProfile]);

  const handleSearch = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    const sym = input.trim().toUpperCase();
    if (sym) {
      setSymbol(sym);
      setInput('');
    }
  };

  if (loading) return <PanelChrome title="Company Profile" icon={Building} iconColor="var(--blue)"><PanelSkeleton /></PanelChrome>;

  return (
    <PanelChrome title={profile?.companyName || symbol} icon={Building} iconColor="var(--blue)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%', minHeight: 0, overflow: 'auto' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 4 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={10} style={{ position: 'absolute', left: 6, top: 6, color: 'var(--text-3)' }} />
            <input
              value={input}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setInput(e.target.value)}
              placeholder="Search ticker..."
              style={{ width: '100%', background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 4, color: 'var(--text-1)', fontSize: 10, padding: '4px 6px 4px 20px', fontFamily: 'var(--font-mono)' }}
            />
          </div>
        </form>

        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {POPULAR.map(s => (
            <button key={s} className="btn-ghost" onClick={() => setSymbol(s)}
              style={{ fontSize: 9, padding: '1px 5px', color: symbol === s ? 'var(--cyan)' : 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
              {s}
            </button>
          ))}
        </div>

        {!profile ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 11 }}>
            No data for {symbol}. Try a popular ticker above.
          </div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <StatCard label="Market Cap" value={formatMktCap(profile.mktCap)} />
              <StatCard label="Sector" value={profile.sector || 'N/A'} />
              <StatCard label="Industry" value={profile.industry || 'N/A'} />
              <StatCard label="Exchange" value={profile.exchange || 'N/A'} />
              <StatCard label="Beta" value={(Number(profile.beta) || 0).toFixed(2)} />
              <StatCard label="CEO" value={profile.ceo || 'N/A'} />
            </div>

            {profile.description && (
              <div style={{ fontSize: 10, color: 'var(--text-3)', lineHeight: 1.5 }}>
                {profile.description.slice(0, 300)}{profile.description.length > 300 ? '...' : ''}
              </div>
            )}

            {profile.website && (
              <a href={profile.website} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 10, color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 4, textDecoration: 'none' }}>
                <ExternalLink size={10} /> {profile.website.replace(/^https?:\/\//, '')}
              </a>
            )}
          </>
        )}
      </div>
    </PanelChrome>
  );
});

interface StatCardProps {
  label: string;
  value: string;
}

function StatCard({ label, value }: StatCardProps): ReactElement {
  return (
    <div style={{ background: 'var(--bg-1)', borderRadius: 5, padding: '6px 8px', border: '1px solid var(--border-1)' }}>
      <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-1)' }}>{value}</div>
    </div>
  );
}

PanelCompany.displayName = "PanelCompany";
export default PanelCompany;
