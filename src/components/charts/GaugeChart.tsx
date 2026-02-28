import { memo, type ReactElement } from 'react';

interface GaugeZone {
  start: number;
  end: number;
  color: string;
}

interface GaugeChartProps {
  value?: number;
  min?: number;
  max?: number;
  label?: string;
  size?: number;
  zones?: GaugeZone[];
}

const GaugeChart = memo(({ value = 50, min = 0, max = 100, label, size = 80, zones }: GaugeChartProps): ReactElement => {
  const pct = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const angle = -135 + pct * 270;
  const r = size / 2 - 8;
  const cx = size / 2, cy = size / 2;

  const defaultZones: GaugeZone[] = zones || [
    { start: 0, end: 0.3, color: 'var(--red)' },
    { start: 0.3, end: 0.7, color: 'var(--amber)' },
    { start: 0.7, end: 1, color: 'var(--green)' },
  ];

  const arcPath = (startPct: number, endPct: number): string => {
    const startAngle = (-135 + startPct * 270) * Math.PI / 180;
    const endAngle = (-135 + endPct * 270) * Math.PI / 180;
    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const large = (endPct - startPct) * 270 > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  const needleAngle = angle * Math.PI / 180;
  const nx = cx + (r - 10) * Math.cos(needleAngle);
  const ny = cy + (r - 10) * Math.sin(needleAngle);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <svg width={size} height={size * 0.7} viewBox={`0 0 ${size} ${size * 0.75}`}>
        {defaultZones.map((z, i) => (
          <path key={i} d={arcPath(z.start, z.end)} fill="none" stroke={z.color} strokeWidth={4} strokeLinecap="round" opacity={0.3} />
        ))}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--text-1)" strokeWidth={2} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={3} fill="var(--text-1)" />
      </svg>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'JetBrains Mono' }}>
        {typeof value === 'number' ? value.toFixed(1) : value}
      </div>
      {label && <div style={{ fontSize: 9, color: 'var(--text-4)' }}>{label}</div>}
    </div>
  );
});
GaugeChart.displayName = 'GaugeChart';
export default GaugeChart;
