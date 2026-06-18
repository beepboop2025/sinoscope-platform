import { useState, memo, type ReactElement } from 'react';
import { Globe } from 'lucide-react';
import { BRI_COUNTRIES, BRI_CORRIDORS } from '../../../constants/china';
import PanelChrome from '../../shared/PanelChrome';

interface Region {
  id: string; name: string; x: number; y: number; projects: number; type: string; flagship?: boolean;
}

interface CorridorPath {
  name: string; d: string; color: string; width: number;
}

interface Corridor {
  name: string; investment: string; projects: number; route: string; status: string;
}

const REGIONS: Region[] = [
  { id: 'china', name: 'China', x: 75, y: 35, projects: 0, type: 'hub' },
  { id: 'mongolia', name: 'Mongolia', x: 78, y: 28, projects: 32, type: 'country' },
  { id: 'vietnam', name: 'Vietnam', x: 72, y: 45, projects: 56, type: 'country' },
  { id: 'thailand', name: 'Thailand', x: 70, y: 48, projects: 78, type: 'country' },
  { id: 'myanmar', name: 'Myanmar', x: 68, y: 46, projects: 42, type: 'country' },
  { id: 'laos', name: 'Laos', x: 70, y: 45, projects: 67, type: 'country' },
  { id: 'cambodia', name: 'Cambodia', x: 71, y: 47, projects: 38, type: 'country' },
  { id: 'malaysia', name: 'Malaysia', x: 70, y: 55, projects: 67, type: 'country' },
  { id: 'singapore', name: 'Singapore', x: 70, y: 58, projects: 34, type: 'country' },
  { id: 'indonesia', name: 'Indonesia', x: 75, y: 65, projects: 89, type: 'country' },
  { id: 'philippines', name: 'Philippines', x: 78, y: 48, projects: 45, type: 'country' },
  { id: 'pakistan', name: 'Pakistan', x: 58, y: 38, projects: 92, type: 'country', flagship: true },
  { id: 'bangladesh', name: 'Bangladesh', x: 62, y: 42, projects: 48, type: 'country' },
  { id: 'srilanka', name: 'Sri Lanka', x: 60, y: 52, projects: 34, type: 'country' },
  { id: 'nepal', name: 'Nepal', x: 60, y: 40, projects: 23, type: 'country' },
  { id: 'kazakhstan', name: 'Kazakhstan', x: 55, y: 25, projects: 56, type: 'country' },
  { id: 'uzbekistan', name: 'Uzbekistan', x: 52, y: 32, projects: 45, type: 'country' },
  { id: 'kyrgyzstan', name: 'Kyrgyzstan', x: 58, y: 32, projects: 28, type: 'country' },
  { id: 'tajikistan', name: 'Tajikistan', x: 55, y: 35, projects: 21, type: 'country' },
  { id: 'iran', name: 'Iran', x: 45, y: 38, projects: 38, type: 'country' },
  { id: 'turkey', name: 'Turkey', x: 38, y: 35, projects: 51, type: 'country' },
  { id: 'uae', name: 'UAE', x: 45, y: 45, projects: 54, type: 'country' },
  { id: 'saudi', name: 'Saudi Arabia', x: 40, y: 45, projects: 48, type: 'country' },
  { id: 'egypt', name: 'Egypt', x: 35, y: 42, projects: 42, type: 'country' },
  { id: 'russia', name: 'Russia', x: 65, y: 15, projects: 78, type: 'country' },
  { id: 'poland', name: 'Poland', x: 42, y: 22, projects: 31, type: 'country' },
  { id: 'italy', name: 'Italy', x: 32, y: 30, projects: 34, type: 'country' },
  { id: 'greece', name: 'Greece', x: 36, y: 32, projects: 28, type: 'country' },
  { id: 'hungary', name: 'Hungary', x: 38, y: 27, projects: 24, type: 'country' },
  { id: 'kenya', name: 'Kenya', x: 48, y: 60, projects: 56, type: 'country', flagship: true },
  { id: 'ethiopia', name: 'Ethiopia', x: 46, y: 55, projects: 42, type: 'country' },
  { id: 'southafrica', name: 'South Africa', x: 42, y: 80, projects: 38, type: 'country' },
  { id: 'nigeria', name: 'Nigeria', x: 35, y: 55, projects: 45, type: 'country' },
];

const CORRIDOR_PATHS: CorridorPath[] = [
  { name: 'CPEC', d: 'M 75 35 L 65 38 L 58 38', color: '#ef4444', width: 3 },
  { name: 'Eurasian Land Bridge', d: 'M 75 35 L 70 25 L 55 25 L 42 22', color: '#3b82f6', width: 3 },
  { name: 'China-Mongolia-Russia', d: 'M 75 35 L 78 28 L 70 18 L 65 15', color: '#10b981', width: 2 },
  { name: 'Indochina Peninsula', d: 'M 75 35 L 72 45 L 70 48 L 70 58', color: '#f59e0b', width: 2 },
  { name: 'China-Myanmar', d: 'M 75 35 L 72 42 L 68 46', color: '#8b5cf6', width: 2 },
  { name: 'East Africa', d: 'M 75 35 L 70 50 L 60 58 L 48 60', color: '#ec4899', width: 2 },
];

const PanelBeltRoad = memo(function PanelBeltRoad(): ReactElement {
  const [selectedCorridor, setSelectedCorridor] = useState<Corridor | null>(null);
  const [hoveredCountry, setHoveredCountry] = useState<Region | null>(null);

  const totalProjects = REGIONS.reduce((sum, r) => sum + (r.projects || 0), 0);
  const totalInvestment = (BRI_CORRIDORS as Corridor[]).reduce((sum, c) => {
    const val = parseFloat(c.investment.replace(/[$B]/g, ''));
    return sum + val;
  }, 0);

  const getCountryColor = (country: Region): string => {
    if (country.type === 'hub') return 'var(--red)';
    if (country.flagship) return 'var(--amber)';
    if (!country.projects) return 'var(--surface-3)';
    const intensity = Math.min(country.projects / 100, 1);
    return `rgba(59, 130, 246, ${0.3 + intensity * 0.7})`;
  };

  return (
    <PanelChrome title="Belt & Road Initiative" icon={Globe} iconColor="var(--cyan)">
      <div style={{ padding: 4 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
        <div style={{ padding: 10, background: 'var(--surface-2)', borderRadius: 8, textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--cyan)' }}>${totalInvestment}B+</div>
          <div style={{ fontSize: 9, color: 'var(--text-3)' }}>Total Investment</div>
        </div>
        <div style={{ padding: 10, background: 'var(--surface-2)', borderRadius: 8, textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--green)' }}>{totalProjects}+</div>
          <div style={{ fontSize: 9, color: 'var(--text-3)' }}>Projects</div>
        </div>
        <div style={{ padding: 10, background: 'var(--surface-2)', borderRadius: 8, textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--magenta)' }}>{(BRI_CORRIDORS as Corridor[]).length}</div>
          <div style={{ fontSize: 9, color: 'var(--text-3)' }}>Corridors</div>
        </div>
      </div>

      <div style={{ position: 'relative', height: 200, background: 'var(--surface-1)', borderRadius: 8, overflow: 'hidden', marginBottom: 12 }}>
        <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%' }}>
          {[...Array(10)].map((_, i) => (
            <g key={i}>
              <line x1={i * 10} y1="0" x2={i * 10} y2="100" stroke="var(--divider)" strokeWidth="0.2" opacity="0.3" />
              <line x1="0" y1={i * 10} x2="100" y2={i * 10} stroke="var(--divider)" strokeWidth="0.2" opacity="0.3" />
            </g>
          ))}
          {CORRIDOR_PATHS.map((corridor, idx) => (
            <path key={idx} d={corridor.d} fill="none" stroke={corridor.color} strokeWidth={corridor.width * 0.3}
              opacity={selectedCorridor && selectedCorridor.name !== corridor.name ? 0.2 : 0.8} style={{ transition: 'opacity 0.2s' }} />
          ))}
          {REGIONS.map((country) => (
            <g key={country.id} onMouseEnter={() => setHoveredCountry(country)} onMouseLeave={() => setHoveredCountry(null)} style={{ cursor: 'pointer' }}>
              <circle cx={country.x} cy={country.y} r={country.type === 'hub' ? 4 : country.flagship ? 3.5 : 2 + (country.projects || 0) / 50}
                fill={getCountryColor(country)} stroke={hoveredCountry?.id === country.id ? 'white' : 'none'} strokeWidth="0.5" />
              {country.flagship && <circle cx={country.x} cy={country.y} r={5} fill="none" stroke="var(--amber)" strokeWidth="0.5" opacity="0.5" />}
            </g>
          ))}
        </svg>
        {hoveredCountry && (
          <div style={{ position: 'absolute', left: `${hoveredCountry.x}%`, top: `${hoveredCountry.y - 10}%`, transform: 'translate(-50%, -100%)',
            background: 'var(--surface-2)', padding: '6px 10px', borderRadius: 4, border: '1px solid var(--divider)', fontSize: 11, pointerEvents: 'none', zIndex: 10 }}>
            <div style={{ fontWeight: 600 }}>{hoveredCountry.name}</div>
            {hoveredCountry.projects > 0 && <div style={{ color: 'var(--text-3)' }}>{hoveredCountry.projects} projects</div>}
            {hoveredCountry.flagship && <div style={{ color: 'var(--amber)', fontSize: 9 }}>Flagship Project</div>}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12, fontSize: 9, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 8, height: 8, background: 'var(--red)', borderRadius: '50%' }} /><span>China (Hub)</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 8, height: 8, background: 'var(--amber)', borderRadius: '50%' }} /><span>Flagship Project</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 8, height: 8, background: 'rgba(59, 130, 246, 0.7)', borderRadius: '50%' }} /><span>BRI Participant</span></div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-2)' }}>Major Economic Corridors</div>
        {(BRI_CORRIDORS as Corridor[]).map((corridor, idx) => (
          <div key={idx} onClick={() => setSelectedCorridor(selectedCorridor?.name === corridor.name ? null : corridor)}
            style={{ padding: '8px 10px', background: selectedCorridor?.name === corridor.name ? 'var(--surface-2)' : 'var(--surface-1)',
              borderRadius: 6, border: `1px solid ${selectedCorridor?.name === corridor.name ? 'var(--primary)' : 'var(--divider)'}`, cursor: 'pointer', transition: 'all 0.2s' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: 11, fontWeight: 500 }}>{corridor.name}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 10, color: 'var(--green)', fontWeight: 500 }}>{corridor.investment}</span>
                <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{corridor.projects} projects</span>
              </div>
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-3)', marginTop: 2 }}>{corridor.route}</div>
          </div>
        ))}
      </div>

      {selectedCorridor && (
        <div style={{ marginTop: 12, padding: 12, background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--primary)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>{selectedCorridor.name}</div>
          <div style={{ fontSize: 10, color: 'var(--text-2)', marginBottom: 6 }}>Route: {selectedCorridor.route}</div>
          <div style={{ display: 'flex', gap: 16, fontSize: 10 }}>
            <span style={{ color: 'var(--green)' }}>Investment: {selectedCorridor.investment}</span>
            <span style={{ color: 'var(--cyan)' }}>Projects: {selectedCorridor.projects}</span>
            <span style={{ color: 'var(--amber)' }}>Status: {selectedCorridor.status}</span>
          </div>
        </div>
      )}
    </div>
    </PanelChrome>
  );
});
PanelBeltRoad.displayName = 'PanelBeltRoad';
export default PanelBeltRoad;
