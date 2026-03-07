/**
 * PanelReadiness — ReadyState integration panel
 *
 * Embeds personal readiness assessment with market-driven threat analysis.
 * Syncs checklist state via localStorage (key: readystate-data) with the
 * standalone ReadyState app.
 */

import { memo, useState, useEffect, useMemo, useCallback, type ReactElement } from 'react';
import { Shield, ChevronDown, ChevronRight, Check } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import type { MarketSnapshot, BondYield, EconomicDataPoint } from '../../types/market';

// ─── Types ─────────────────────────────────────────────────────────

interface ChecklistItem {
  readonly id: string;
  readonly text: string;
  readonly weight: number;
}

interface DomainCategory {
  readonly name: string;
  readonly items: readonly ChecklistItem[];
}

interface DomainDef {
  readonly id: string;
  readonly name: string;
  readonly color: string;
  readonly categories: readonly DomainCategory[];
}

interface ThreatFactor {
  text: string;
  impact: 'high' | 'medium' | 'low';
}

interface ThreatResult {
  level: number;
  label: string;
  factors: ThreatFactor[];
}

interface SerializedState {
  checkedIds?: string[];
  [key: string]: unknown;
}

// ─── Constants ─────────────────────────────────────────────────────

const STORAGE_KEY = 'readystate-data';

const SCORE_THRESHOLDS = { STRONG: 80, MODERATE: 60, DEVELOPING: 40, VULNERABLE: 20 } as const;
const THREAT_THRESHOLDS = { CRITICAL: 75, ELEVATED: 55, MODERATE: 35, LOW: 15 } as const;

// ─── Domain Data (mirrors ReadyState's 73 items) ───────────────────

const DOMAINS: DomainDef[] = [
  {
    id: 'financial', name: 'Financial', color: '#10b981',
    categories: [
      { name: 'Emergency Savings', items: [
        { id: 'fin-01', text: 'Emergency fund covers 1 month of expenses', weight: 2 },
        { id: 'fin-02', text: 'Emergency fund covers 3+ months of expenses', weight: 3 },
        { id: 'fin-03', text: 'Emergency cash at home ($200–500)', weight: 2 },
      ]},
      { name: 'Insurance', items: [
        { id: 'fin-04', text: 'Health insurance is active and covers major events', weight: 3 },
        { id: 'fin-05', text: "Renter's or homeowner's insurance is current", weight: 2 },
        { id: 'fin-06', text: 'Auto / transportation insurance is current', weight: 2 },
        { id: 'fin-07', text: 'Life insurance or income protection (if dependents)', weight: 2 },
      ]},
      { name: 'Debt & Income', items: [
        { id: 'fin-08', text: 'Debt-to-income ratio is below 40%', weight: 2 },
        { id: 'fin-09', text: 'Have at least one secondary income source or skill', weight: 2 },
        { id: 'fin-10', text: 'Essential bills can be paid for 2+ months if income stops', weight: 3 },
      ]},
      { name: 'Estate & Documents', items: [
        { id: 'fin-11', text: 'Will or testament is written and accessible', weight: 1 },
        { id: 'fin-12', text: 'Beneficiaries are updated on all financial accounts', weight: 1 },
        { id: 'fin-13', text: 'Important financial documents are stored securely', weight: 2 },
      ]},
    ],
  },
  {
    id: 'supplies', name: 'Supplies', color: '#f59e0b',
    categories: [
      { name: 'Water & Food', items: [
        { id: 'sup-01', text: 'At least 3 days of drinking water stored', weight: 3 },
        { id: 'sup-02', text: 'Non-perishable food for 3+ days', weight: 3 },
        { id: 'sup-03', text: 'Water purification method available', weight: 2 },
        { id: 'sup-04', text: '7+ days of food and water stored', weight: 2 },
      ]},
      { name: 'Medical & First Aid', items: [
        { id: 'sup-05', text: 'Well-stocked first aid kit', weight: 3 },
        { id: 'sup-06', text: '30-day supply of prescription medications', weight: 3 },
        { id: 'sup-07', text: 'Basic OTC medications', weight: 2 },
      ]},
      { name: 'Tools & Power', items: [
        { id: 'sup-08', text: 'Flashlight with extra batteries', weight: 2 },
        { id: 'sup-09', text: 'Battery bank / portable charger for phone', weight: 2 },
        { id: 'sup-10', text: 'Basic tool kit', weight: 1 },
        { id: 'sup-11', text: 'Fire extinguisher (inspected, not expired)', weight: 2 },
      ]},
      { name: 'Documents & Go-Bag', items: [
        { id: 'sup-12', text: 'Copies of vital documents in waterproof container', weight: 2 },
        { id: 'sup-13', text: 'Go-bag packed and ready (72-hour bag)', weight: 2 },
        { id: 'sup-14', text: 'Pet supplies included in emergency plan', weight: 1 },
      ]},
    ],
  },
  {
    id: 'digital', name: 'Digital', color: '#3b82f6',
    categories: [
      { name: 'Passwords & Access', items: [
        { id: 'dig-01', text: 'Using a password manager for all accounts', weight: 3 },
        { id: 'dig-02', text: 'All critical accounts have unique, strong passwords', weight: 3 },
        { id: 'dig-03', text: '2FA enabled on email, banking, and social media', weight: 3 },
        { id: 'dig-04', text: 'Recovery codes for 2FA stored securely offline', weight: 2 },
      ]},
      { name: 'Backups', items: [
        { id: 'dig-05', text: 'Important files backed up to cloud storage', weight: 3 },
        { id: 'dig-06', text: 'Local backup exists (external drive or NAS)', weight: 2 },
        { id: 'dig-07', text: 'Phone photos and contacts are automatically backed up', weight: 2 },
        { id: 'dig-08', text: 'Backup tested — you know you can restore from it', weight: 2 },
      ]},
      { name: 'Account Security', items: [
        { id: 'dig-09', text: 'Email account has recovery email and phone number', weight: 2 },
        { id: 'dig-10', text: 'Know which accounts are linked to which email', weight: 1 },
        { id: 'dig-11', text: 'Digital legacy / account handover plan exists', weight: 1 },
        { id: 'dig-12', text: 'Devices are encrypted', weight: 2 },
      ]},
    ],
  },
  {
    id: 'health', name: 'Health', color: '#f43f5e',
    categories: [
      { name: 'Medical Records', items: [
        { id: 'hlt-01', text: 'Complete list of current medications and dosages', weight: 3 },
        { id: 'hlt-02', text: 'Known allergies documented', weight: 3 },
        { id: 'hlt-03', text: 'Blood type is known and documented', weight: 1 },
        { id: 'hlt-04', text: 'Vaccination records are up to date', weight: 2 },
        { id: 'hlt-05', text: 'Regular health checkup within the last 12 months', weight: 2 },
      ]},
      { name: 'Physical Readiness', items: [
        { id: 'hlt-06', text: 'Can walk/jog 1+ mile without stopping', weight: 2 },
        { id: 'hlt-07', text: 'Maintain a regular exercise routine (3+ times/week)', weight: 2 },
        { id: 'hlt-08', text: 'No chronic conditions are unmanaged', weight: 3 },
      ]},
      { name: 'Mental & Emotional', items: [
        { id: 'hlt-09', text: 'Have a stress management practice', weight: 2 },
        { id: 'hlt-10', text: 'Know signs of mental health crisis and where to get help', weight: 2 },
        { id: 'hlt-11', text: 'Sleep quality is generally good (6-8 hours)', weight: 1 },
      ]},
    ],
  },
  {
    id: 'skills', name: 'Skills', color: '#8b5cf6',
    categories: [
      { name: 'Emergency Skills', items: [
        { id: 'skl-01', text: 'Know basic first aid', weight: 3 },
        { id: 'skl-02', text: 'Know CPR', weight: 3 },
        { id: 'skl-03', text: 'Can use a fire extinguisher (PASS technique)', weight: 2 },
        { id: 'skl-04', text: 'Know how to shut off home utilities', weight: 2 },
      ]},
      { name: 'Self-Sufficiency', items: [
        { id: 'skl-05', text: 'Can cook basic meals from non-perishable ingredients', weight: 2 },
        { id: 'skl-06', text: 'Can perform basic home repairs', weight: 1 },
        { id: 'skl-07', text: 'Can navigate without GPS', weight: 1 },
        { id: 'skl-08', text: 'Basic self-defense awareness', weight: 1 },
      ]},
      { name: 'Career Resilience', items: [
        { id: 'skl-09', text: 'Resume / portfolio is updated within the last 6 months', weight: 2 },
        { id: 'skl-10', text: 'Have skills that transfer across industries', weight: 2 },
        { id: 'skl-11', text: 'Currently learning something new', weight: 1 },
        { id: 'skl-12', text: 'Understand basics of AI tools relevant to your field', weight: 2 },
      ]},
    ],
  },
  {
    id: 'network', name: 'Network', color: '#06b6d4',
    categories: [
      { name: 'Emergency Contacts', items: [
        { id: 'net-01', text: 'ICE contacts saved in phone', weight: 3 },
        { id: 'net-02', text: 'Emergency contacts know your medical conditions', weight: 2 },
        { id: 'net-03', text: 'Contact list exists on paper (not just in phone)', weight: 2 },
        { id: 'net-04', text: 'Have a designated out-of-area contact', weight: 2 },
      ]},
      { name: 'Community', items: [
        { id: 'net-05', text: 'Know at least 3 neighbors by name', weight: 2 },
        { id: 'net-06', text: 'Part of a local community group', weight: 1 },
        { id: 'net-07', text: 'Know location of nearest hospital, fire station, shelter', weight: 2 },
      ]},
      { name: 'Plans & Communication', items: [
        { id: 'net-08', text: 'Family/household emergency plan exists', weight: 3 },
        { id: 'net-09', text: 'Meeting point designated in case of evacuation', weight: 2 },
        { id: 'net-10', text: 'Communication plan if phone/internet is down', weight: 2 },
        { id: 'net-11', text: 'Someone outside your household has copies of documents', weight: 1 },
      ]},
    ],
  },
];

// ─── Scoring ───────────────────────────────────────────────────────

function calcDomainScore(domain: DomainDef, checkedIds: Set<string>): number {
  let earned = 0, total = 0;
  for (const cat of domain.categories) {
    for (const item of cat.items) {
      total += item.weight;
      if (checkedIds.has(item.id)) earned += item.weight;
    }
  }
  return total === 0 ? 0 : Math.round((earned / total) * 100);
}

function calcOverallScore(checkedIds: Set<string>): number {
  const scores = DOMAINS.map(d => calcDomainScore(d, checkedIds));
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
}

function scoreLabel(score: number): string {
  if (score >= SCORE_THRESHOLDS.STRONG) return 'Strong';
  if (score >= SCORE_THRESHOLDS.MODERATE) return 'Moderate';
  if (score >= SCORE_THRESHOLDS.DEVELOPING) return 'Developing';
  if (score >= SCORE_THRESHOLDS.VULNERABLE) return 'Vulnerable';
  return 'Critical';
}

function scoreColor(score: number): string {
  if (score >= SCORE_THRESHOLDS.STRONG) return '#10b981';
  if (score >= SCORE_THRESHOLDS.MODERATE) return '#eab308';
  if (score >= SCORE_THRESHOLDS.DEVELOPING) return '#f59e0b';
  if (score >= SCORE_THRESHOLDS.VULNERABLE) return '#f43f5e';
  return '#ef4444';
}

// ─── Threat Computation (adapts MarketSnapshot → threat score) ─────

function getLatestValue(series: EconomicDataPoint[] | undefined): number | null {
  if (!series || series.length === 0) return null;
  return series[series.length - 1].value;
}

function computeThreat(data: MarketSnapshot | null): ThreatResult {
  if (!data) return { level: 30, label: 'Unknown', factors: [{ text: 'No market data available', impact: 'low' }] };

  let score = 30;
  const factors: ThreatFactor[] = [];

  // Fear & Greed — check if economic has a fear_greed series
  const fgSeries = data.economic?.['fear_greed'] ?? data.economic?.['FEAR_GREED'];
  const fgValue = getLatestValue(fgSeries);
  if (fgValue != null) {
    if (fgValue <= 20) { score += 25; factors.push({ text: `Extreme Fear (${fgValue}/100)`, impact: 'high' }); }
    else if (fgValue <= 35) { score += 15; factors.push({ text: `Fear (${fgValue}/100)`, impact: 'medium' }); }
    else if (fgValue >= 80) { score += 10; factors.push({ text: `Extreme Greed (${fgValue}) — bubble risk`, impact: 'medium' }); }
  }

  // Yield curve inversion
  if (data.bonds && data.bonds.length > 0) {
    const y2 = data.bonds.find((b: BondYield) => b.maturity === '2Y' || b.maturity === '2 Year');
    const y10 = data.bonds.find((b: BondYield) => b.maturity === '10Y' || b.maturity === '10 Year');
    if (y2 && y10) {
      const spread = y10.yield - y2.yield;
      if (spread < 0) {
        score += 20;
        factors.push({ text: `Yield curve INVERTED (${spread.toFixed(2)}%) — recession signal`, impact: 'high' });
      } else if (spread < 0.3) {
        score += 8;
        factors.push({ text: `Yield curve flattening (${spread.toFixed(2)}%)`, impact: 'medium' });
      }
    }
  }

  // Unemployment
  const unempValue = getLatestValue(data.economic?.['UNRATE'] ?? data.economic?.['unemployment']);
  if (unempValue != null) {
    if (unempValue > 6) { score += 15; factors.push({ text: `High unemployment (${unempValue}%)`, impact: 'high' }); }
    else if (unempValue > 4.5) { score += 8; factors.push({ text: `Rising unemployment (${unempValue}%)`, impact: 'medium' }); }
  }

  // CPI / Inflation
  const cpiValue = getLatestValue(data.economic?.['CPIAUCSL'] ?? data.economic?.['cpi']);
  if (cpiValue != null) {
    if (cpiValue > 5) { score += 12; factors.push({ text: `High inflation (CPI ${cpiValue})`, impact: 'high' }); }
    else if (cpiValue > 3.5) { score += 6; factors.push({ text: `Elevated inflation (CPI ${cpiValue})`, impact: 'medium' }); }
  }

  // GDP
  const gdpValue = getLatestValue(data.economic?.['GDP'] ?? data.economic?.['gdp']);
  if (gdpValue != null && gdpValue < 0) {
    score += 15;
    factors.push({ text: 'GDP contracting — recession territory', impact: 'high' });
  }

  // If no factors were added, show baseline
  if (factors.length === 0) {
    factors.push({ text: 'Baseline market conditions', impact: 'low' });
  }

  const level = Math.max(0, Math.min(100, Math.round(score)));
  return { level, label: threatLabel(level), factors };
}

function threatLabel(score: number): string {
  if (score >= THREAT_THRESHOLDS.CRITICAL) return 'Critical';
  if (score >= THREAT_THRESHOLDS.ELEVATED) return 'Elevated';
  if (score >= THREAT_THRESHOLDS.MODERATE) return 'Moderate';
  if (score >= THREAT_THRESHOLDS.LOW) return 'Low';
  return 'Minimal';
}

function threatColor(score: number): string {
  if (score >= THREAT_THRESHOLDS.CRITICAL) return '#ef4444';
  if (score >= THREAT_THRESHOLDS.ELEVATED) return '#f59e0b';
  if (score >= THREAT_THRESHOLDS.MODERATE) return '#eab308';
  return '#10b981';
}

function effectiveRiskColor(risk: number): string {
  if (risk >= 60) return '#ef4444';
  if (risk >= 30) return '#f59e0b';
  return '#10b981';
}

// ─── SVG Gauge ─────────────────────────────────────────────────────

function GaugeArc({ score, size = 120 }: { score: number; size?: number }): ReactElement {
  const r = 45;
  const circumference = Math.PI * r; // semicircle
  const offset = circumference - (score / 100) * circumference;
  const color = scoreColor(score);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={size} height={size * 0.6} viewBox="0 0 120 72" aria-hidden="true">
        {/* Background arc */}
        <path
          d="M 15 60 A 45 45 0 0 1 105 60"
          fill="none"
          stroke="var(--bg-3)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Score arc */}
        <path
          d="M 15 60 A 45 45 0 0 1 105 60"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
        {/* Score text */}
        <text x="60" y="52" textAnchor="middle" fill="var(--text-1)" fontSize="22" fontWeight="700" fontFamily="var(--font-mono)">
          {score}
        </text>
        <text x="60" y="67" textAnchor="middle" fill={color} fontSize="8" fontWeight="600" letterSpacing="1">
          {scoreLabel(score).toUpperCase()}
        </text>
      </svg>
      <span style={{ fontSize: 9, color: 'var(--text-3)', letterSpacing: 1 }}>READINESS</span>
    </div>
  );
}

// ─── SVG Radar Chart ───────────────────────────────────────────────

function RadarChart({ domainScores, size = 160 }: { domainScores: Record<string, number>; size?: number }): ReactElement {
  const cx = size / 2;
  const cy = size / 2;
  const maxR = size * 0.38;
  const n = DOMAINS.length;

  function polarToCart(angle: number, radius: number): [number, number] {
    const rad = (angle - 90) * (Math.PI / 180);
    return [cx + radius * Math.cos(rad), cy + radius * Math.sin(rad)];
  }

  const angles = DOMAINS.map((_, i) => (360 / n) * i);

  // Grid rings at 25%, 50%, 75%, 100%
  const rings = [0.25, 0.5, 0.75, 1.0];

  // Score polygon
  const scorePoints = DOMAINS.map((d, i) => {
    const val = (domainScores[d.id] || 0) / 100;
    return polarToCart(angles[i], maxR * val);
  });
  const scorePath = scorePoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ') + ' Z';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        {/* Grid rings */}
        {rings.map(r => {
          const pts = angles.map(a => polarToCart(a, maxR * r));
          const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ') + ' Z';
          return <path key={r} d={d} fill="none" stroke="var(--bg-3)" strokeWidth="0.5" />;
        })}

        {/* Axis lines */}
        {angles.map((a, i) => {
          const [ex, ey] = polarToCart(a, maxR);
          return <line key={i} x1={cx} y1={cy} x2={ex} y2={ey} stroke="var(--bg-3)" strokeWidth="0.5" />;
        })}

        {/* Score polygon */}
        <path d={scorePath} fill="var(--cyan)" fillOpacity="0.15" stroke="var(--cyan)" strokeWidth="1.5" />

        {/* Score dots + labels */}
        {DOMAINS.map((d, i) => {
          const val = (domainScores[d.id] || 0) / 100;
          const [dx, dy] = polarToCart(angles[i], maxR * val);
          const [lx, ly] = polarToCart(angles[i], maxR + 14);
          return (
            <g key={d.id}>
              <circle cx={dx} cy={dy} r="3" fill={d.color} />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="central" fill="var(--text-3)" fontSize="7" fontWeight="500">
                {d.name.slice(0, 3).toUpperCase()}
              </text>
            </g>
          );
        })}
      </svg>
      <span style={{ fontSize: 9, color: 'var(--text-3)', letterSpacing: 1 }}>DOMAIN COVERAGE</span>
    </div>
  );
}

// ─── Domain Bar ────────────────────────────────────────────────────

function DomainBar({ domain, score, onClick, isExpanded }: {
  domain: DomainDef;
  score: number;
  onClick: () => void;
  isExpanded: boolean;
}): ReactElement {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%',
        padding: '4px 0', background: 'none', border: 'none', cursor: 'pointer',
        color: 'var(--text-1)', fontSize: 11, fontFamily: 'inherit',
      }}
      aria-expanded={isExpanded}
      aria-label={`${domain.name}: ${score}%`}
    >
      {isExpanded ? <ChevronDown size={10} color="var(--text-3)" /> : <ChevronRight size={10} color="var(--text-3)" />}
      <span style={{ width: 60, textAlign: 'left', fontWeight: 500, color: domain.color }}>{domain.name}</span>
      <div style={{ flex: 1, height: 6, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%', width: `${score}%`, background: domain.color,
            borderRadius: 3, transition: 'width 0.5s ease-out',
          }}
        />
      </div>
      <span style={{ width: 32, textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 10, color: scoreColor(score) }}>
        {score}%
      </span>
    </button>
  );
}

// ─── Checklist Item ────────────────────────────────────────────────

function CheckItem({ item, checked, onToggle }: {
  item: ChecklistItem;
  checked: boolean;
  onToggle: () => void;
}): ReactElement {
  return (
    <label
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 6, padding: '3px 0 3px 18px',
        cursor: 'pointer', fontSize: 10, color: checked ? 'var(--text-3)' : 'var(--text-2)',
        textDecoration: checked ? 'line-through' : 'none',
      }}
    >
      <span
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 14, height: 14, minWidth: 14,
          borderRadius: 3, marginTop: 1,
          border: checked ? 'none' : '1px solid var(--text-4)',
          background: checked ? 'var(--cyan)' : 'transparent',
          transition: 'all 0.15s',
        }}
      >
        {checked && <Check size={10} color="var(--bg-1)" strokeWidth={3} />}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        style={{ display: 'none' }}
        aria-label={item.text}
      />
      <span style={{ lineHeight: 1.3 }}>{item.text}</span>
      {item.weight >= 3 && (
        <span style={{ fontSize: 8, color: 'var(--red)', fontWeight: 700, marginLeft: 'auto', whiteSpace: 'nowrap' }}>●●●</span>
      )}
      {item.weight === 2 && (
        <span style={{ fontSize: 8, color: 'var(--amber)', fontWeight: 700, marginLeft: 'auto', whiteSpace: 'nowrap' }}>●●</span>
      )}
    </label>
  );
}

// ─── Threat Factors Display ────────────────────────────────────────

function ThreatFactors({ factors }: { factors: ThreatFactor[] }): ReactElement {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
      {factors.slice(0, 5).map((f, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9 }}>
          <span style={{
            width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
            background: f.impact === 'high' ? 'var(--red)' : f.impact === 'medium' ? 'var(--amber)' : 'var(--text-4)',
          }} />
          <span style={{ color: 'var(--text-3)' }}>{f.text}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Main Panel ────────────────────────────────────────────────────

interface PanelReadinessProps {
  data?: MarketSnapshot | null;
}

function PanelReadiness({ data = null }: PanelReadinessProps): ReactElement {
  // Load checklist state from localStorage (synced with ReadyState app)
  const [checkedIds, setCheckedIds] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return new Set<string>();
      const parsed: SerializedState = JSON.parse(raw);
      return new Set(parsed.checkedIds || []);
    } catch {
      return new Set<string>();
    }
  });

  const [expandedDomain, setExpandedDomain] = useState<string | null>(null);
  const [showChecklist, setShowChecklist] = useState(false);

  // Listen for localStorage changes from ReadyState app running in another tab
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key !== STORAGE_KEY) return;
      try {
        const parsed: SerializedState = JSON.parse(e.newValue || '{}');
        setCheckedIds(new Set(parsed.checkedIds || []));
      } catch { /* ignore */ }
    }
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Save to localStorage whenever checkedIds changes
  const saveCheckedIds = useCallback((newIds: Set<string>) => {
    setCheckedIds(newIds);
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const existing: SerializedState = raw ? JSON.parse(raw) : {};
      existing.checkedIds = [...newIds];
      existing.lastUpdated = Date.now();
      localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
    } catch { /* QuotaExceeded */ }
  }, []);

  const toggleItem = useCallback((id: string) => {
    setCheckedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      saveCheckedIds(next);
      return next;
    });
  }, [saveCheckedIds]);

  // Compute scores
  const scores = useMemo(() => {
    const domainScores: Record<string, number> = {};
    for (const d of DOMAINS) {
      domainScores[d.id] = calcDomainScore(d, checkedIds);
    }
    const overall = calcOverallScore(checkedIds);
    return { domainScores, overall };
  }, [checkedIds]);

  // Compute threat from market data
  const threat = useMemo(() => computeThreat(data ?? null), [data]);

  // Effective risk
  const effectiveRisk = Math.round(threat.level * (1 - scores.overall / 100));

  // Count checked / total
  const totalItems = DOMAINS.reduce((sum, d) => sum + d.categories.reduce((s, c) => s + c.items.length, 0), 0);
  const checkedCount = checkedIds.size;

  return (
    <PanelChrome title="Readiness" icon={Shield} iconColor="var(--cyan)">
      <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 12, fontSize: 11 }}>

        {/* ── Top Row: Gauge + Radar + Stats ── */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
          <GaugeArc score={scores.overall} />
          <RadarChart domainScores={scores.domainScores} size={140} />

          {/* Stats column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 120 }}>
            {/* Effective Risk */}
            <div style={{ background: 'var(--bg-2)', borderRadius: 6, padding: '8px 10px' }}>
              <div style={{ fontSize: 8, color: 'var(--text-4)', letterSpacing: 1, marginBottom: 4 }}>EFFECTIVE RISK</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)', color: effectiveRiskColor(effectiveRisk) }}>
                  {effectiveRisk}
                </span>
                <span style={{ fontSize: 9, color: 'var(--text-3)' }}>/100</span>
              </div>
              <div style={{ fontSize: 8, color: 'var(--text-4)', marginTop: 2 }}>
                Threat × (1 − Readiness)
              </div>
            </div>

            {/* Threat Level */}
            <div style={{ background: 'var(--bg-2)', borderRadius: 6, padding: '8px 10px' }}>
              <div style={{ fontSize: 8, color: 'var(--text-4)', letterSpacing: 1, marginBottom: 4 }}>MARKET THREAT</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: threatColor(threat.level) }}>
                  {threat.level}
                </span>
                <span style={{ fontSize: 9, color: threatColor(threat.level), fontWeight: 600 }}>
                  {threat.label}
                </span>
              </div>
              <ThreatFactors factors={threat.factors} />
            </div>

            {/* Progress */}
            <div style={{ fontSize: 9, color: 'var(--text-3)', textAlign: 'center' }}>
              {checkedCount}/{totalItems} items completed
            </div>
          </div>
        </div>

        {/* ── Domain Bars ── */}
        <div>
          <div style={{ fontSize: 9, color: 'var(--text-4)', letterSpacing: 1, marginBottom: 4 }}>DOMAINS</div>
          {DOMAINS.map(d => (
            <div key={d.id}>
              <DomainBar
                domain={d}
                score={scores.domainScores[d.id]}
                isExpanded={expandedDomain === d.id}
                onClick={() => setExpandedDomain(expandedDomain === d.id ? null : d.id)}
              />
              {expandedDomain === d.id && (
                <div style={{ padding: '2px 0 6px 0' }}>
                  {d.categories.map(cat => (
                    <div key={cat.name} style={{ marginBottom: 4 }}>
                      <div style={{ fontSize: 9, color: 'var(--text-4)', padding: '2px 0 2px 18px', fontWeight: 600 }}>
                        {cat.name}
                      </div>
                      {cat.items.map(item => (
                        <CheckItem
                          key={item.id}
                          item={item}
                          checked={checkedIds.has(item.id)}
                          onToggle={() => toggleItem(item.id)}
                        />
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* ── Expand All Toggle ── */}
        <button
          onClick={() => setShowChecklist(!showChecklist)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
            padding: '6px 0', background: 'var(--bg-2)', border: '1px solid var(--bg-3)',
            borderRadius: 4, cursor: 'pointer', color: 'var(--text-3)', fontSize: 10,
            fontFamily: 'inherit', width: '100%',
          }}
        >
          {showChecklist ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          {showChecklist ? 'Collapse Full Checklist' : 'Expand Full Checklist'}
        </button>

        {showChecklist && (
          <div style={{ borderTop: '1px solid var(--bg-3)', paddingTop: 8 }}>
            {DOMAINS.map(d => (
              <div key={d.id} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: d.color, marginBottom: 4 }}>
                  {d.name} — {scores.domainScores[d.id]}%
                </div>
                {d.categories.map(cat => (
                  <div key={cat.name} style={{ marginBottom: 4 }}>
                    <div style={{ fontSize: 9, color: 'var(--text-4)', padding: '2px 0', fontWeight: 600 }}>
                      {cat.name}
                    </div>
                    {cat.items.map(item => (
                      <CheckItem
                        key={item.id}
                        item={item}
                        checked={checkedIds.has(item.id)}
                        onToggle={() => toggleItem(item.id)}
                      />
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* ── Footer ── */}
        <div style={{ fontSize: 8, color: 'var(--text-4)', textAlign: 'center', borderTop: '1px solid var(--bg-3)', paddingTop: 6 }}>
          Powered by ReadyState • Synced via localStorage
        </div>
      </div>
    </PanelChrome>
  );
}

export default memo(PanelReadiness);
