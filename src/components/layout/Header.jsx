import { useState, useEffect, memo } from 'react';
import { Activity, Wifi, WifiOff, Command } from 'lucide-react';
import { TIMEZONES, getTimeInZone } from '../../utils/time';

const ClockDisplay = memo(({ label, tz, abbr }) => {
  const [time, setTime] = useState(getTimeInZone(tz));
  useEffect(() => {
    const id = setInterval(() => setTime(getTimeInZone(tz)), 1000);
    return () => clearInterval(id);
  }, [tz]);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase' }}>{label}</span>
      <span className="mono" style={{ fontSize: 11, color: 'var(--text-1)' }}>{time}</span>
    </div>
  );
});
ClockDisplay.displayName = "ClockDisplay";

export default function Header({ wsStatus, onOpenCommandBar }) {
  const isConnected = wsStatus === 'connected';

  return (
    <div className="app-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Activity size={18} color="var(--cyan)" />
        <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: '0.02em' }}>
          <span style={{ color: 'var(--cyan)' }}>Dragon</span>
          <span style={{ color: 'var(--text-1)' }}>Scope</span>
        </span>
      </div>

      <div style={{ display: 'flex', gap: 16, marginLeft: 24 }}>
        {Object.values(TIMEZONES).map(z => (
          <ClockDisplay key={z.tz} label={z.abbr} tz={z.tz} />
        ))}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          className="btn-ghost"
          onClick={onOpenCommandBar}
          style={{ padding: '4px 10px', fontSize: 11 }}
        >
          <Command size={12} /> <span className="mono">Ctrl+K</span>
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {isConnected ? <Wifi size={14} color="var(--green)" /> : <WifiOff size={14} color="var(--text-4)" />}
          <div className={`status-dot ${isConnected ? 'live' : 'error'}`} />
          <span style={{ fontSize: 10, color: isConnected ? 'var(--green)' : 'var(--text-4)' }}>
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </div>
  );
}
