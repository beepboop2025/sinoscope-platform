import { memo, type ReactElement } from 'react';
import PanelChrome from '../shared/PanelChrome';
import { useSettings } from '../../stores/settings';

interface ToggleRowProps {
  label: string;
  description?: string;
  value: boolean;
  onChange: (v: boolean) => void;
}

function ToggleRow({ label, description, value, onChange }: ToggleRowProps): ReactElement {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '8px 0', borderBottom: '1px solid var(--surface-2, rgba(255,255,255,0.06))',
    }}>
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)' }}>{label}</div>
        {description && <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2 }}>{description}</div>}
      </div>
      <button
        onClick={() => onChange(!value)}
        aria-pressed={value}
        style={{
          width: 36, height: 20, borderRadius: 10, border: 'none', cursor: 'pointer',
          background: value ? 'var(--cyan, #22d3ee)' : 'var(--surface-3, rgba(255,255,255,0.09))',
          position: 'relative', transition: 'background 0.2s',
        }}
      >
        <div style={{
          width: 16, height: 16, borderRadius: '50%', background: 'white',
          position: 'absolute', top: 2,
          left: value ? 18 : 2, transition: 'left 0.2s',
        }} />
      </button>
    </div>
  );
}

interface SliderRowProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (v: number) => void;
}

function SliderRow({ label, value, min, max, step = 1, suffix = '', onChange }: SliderRowProps): ReactElement {
  return (
    <div style={{ padding: '8px 0', borderBottom: '1px solid var(--surface-2, rgba(255,255,255,0.06))' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)' }}>{label}</span>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{value}{suffix}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{ width: '100%', accentColor: 'var(--cyan, #22d3ee)' }}
      />
    </div>
  );
}

function SectionHeader({ title }: { title: string }): ReactElement {
  return (
    <div style={{
      fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em',
      color: 'var(--text-4)', padding: '12px 0 4px',
    }}>
      {title}
    </div>
  );
}

const PanelSettings = memo((): ReactElement => {
  const s = useSettings();

  return (
    <PanelChrome title="Settings" panelId="settings">
      <div style={{ padding: '4px 12px 12px', overflowY: 'auto', maxHeight: '100%' }}>
        <SectionHeader title="Appearance" />
        <ToggleRow label="Animations" description="Enable framer-motion animations" value={s.animationsEnabled} onChange={v => s.setSetting('animationsEnabled', v)} />
        <SliderRow label="Glass Intensity" value={s.glassIntensity} min={0} max={100} suffix="%" onChange={v => s.setSetting('glassIntensity', v)} />

        <SectionHeader title="Gamification" />
        <ToggleRow label="Enable Gamification" description="XP, achievements, streaks" value={s.gamificationEnabled} onChange={v => s.setSetting('gamificationEnabled', v)} />
        <ToggleRow label="Show XP Bar" value={s.showXPBar} onChange={v => s.setSetting('showXPBar', v)} />
        <ToggleRow label="Show Streak" value={s.showStreak} onChange={v => s.setSetting('showStreak', v)} />
        <ToggleRow label="Achievement Sound" description="Play sound on achievement unlock" value={s.soundOnAchievement} onChange={v => s.setSetting('soundOnAchievement', v)} />

        <SectionHeader title="Audio" />
        <ToggleRow label="Sound Effects" description="UI and alert sounds" value={s.soundEnabled} onChange={v => s.setSetting('soundEnabled', v)} />
        <SliderRow label="Volume" value={Math.round(s.soundVolume * 100)} min={0} max={100} suffix="%" onChange={v => s.setSetting('soundVolume', v / 100)} />

        <SectionHeader title="Data" />
        <SliderRow label="Refresh Interval" value={s.refreshInterval} min={1} max={30} suffix="s" onChange={v => s.setSetting('refreshInterval', v)} />
        <ToggleRow label="Mock Data Fallback" description="Use generated data when APIs fail" value={s.useMockFallback} onChange={v => s.setSetting('useMockFallback', v)} />
        <SliderRow label="Cache TTL" value={s.maxCacheAge} min={30} max={600} step={30} suffix="s" onChange={v => s.setSetting('maxCacheAge', v)} />
      </div>
    </PanelChrome>
  );
});
PanelSettings.displayName = 'PanelSettings';
export default PanelSettings;
