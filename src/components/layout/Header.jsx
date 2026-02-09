import { useState, useEffect, memo, lazy, Suspense } from 'react';
import { Activity, Wifi, WifiOff, Command, Sun, Moon, Download } from 'lucide-react';
import { useTheme } from '../shared/ThemeProvider';
import { useInstallPrompt } from '../../hooks/useInstallPrompt';
import { TIMEZONES, getTimeInZone } from '../../utils/time';

const CLERK_ENABLED = !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
const UserMenu = CLERK_ENABLED ? lazy(() => import('../auth/UserMenu')) : null;

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
  const { theme, toggleTheme } = useTheme();
  const { canInstall, promptInstall } = useInstallPrompt();

  return (
    <div className="app-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Activity size={18} color="var(--cyan)" aria-hidden="true" />
        <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: '0.02em' }}>
          <span style={{ color: 'var(--cyan)' }}>Dragon</span>
          <span style={{ color: 'var(--text-1)' }}>Scope</span>
        </span>
      </div>

      <nav role="navigation" aria-label="Timezone clocks" style={{ display: 'flex', gap: 16, marginLeft: 24 }}>
        {Object.values(TIMEZONES).map(z => (
          <ClockDisplay key={z.tz} label={z.abbr} tz={z.tz} />
        ))}
      </nav>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          className="btn-ghost"
          onClick={onOpenCommandBar}
          style={{ padding: '4px 10px', fontSize: 11 }}
          aria-label="Open command bar (Ctrl+K)"
        >
          <Command size={12} aria-hidden="true" /> <span className="mono">Ctrl+K</span>
        </button>

        {canInstall && (
          <button
            className="btn-ghost"
            onClick={promptInstall}
            title="Install DragonScope"
            aria-label="Install DragonScope as app"
            style={{ padding: '4px 10px', fontSize: 11, color: 'var(--cyan)' }}
          >
            <Download size={12} aria-hidden="true" /> <span className="mono">Install</span>
          </button>
        )}

        <button
          className="btn-ghost"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{ padding: '4px 8px' }}
        >
          {theme === 'dark' ? <Sun size={14} aria-hidden="true" /> : <Moon size={14} aria-hidden="true" />}
        </button>

        {UserMenu && (
          <Suspense fallback={null}>
            <UserMenu />
          </Suspense>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }} role="status" aria-live="polite" aria-label={isConnected ? 'WebSocket connected' : 'WebSocket disconnected'}>
          {isConnected ? <Wifi size={14} color="var(--green)" aria-hidden="true" /> : <WifiOff size={14} color="var(--text-4)" aria-hidden="true" />}
          <div className={`status-dot ${isConnected ? 'live' : 'error'}`} aria-hidden="true" />
          <span style={{ fontSize: 10, color: isConnected ? 'var(--green)' : 'var(--text-4)' }}>
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </div>
  );
}
