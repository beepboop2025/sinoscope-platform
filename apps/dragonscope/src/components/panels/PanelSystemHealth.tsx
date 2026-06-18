import { memo, useState, useEffect, useRef, useCallback, type ReactElement } from 'react';
import { Activity, Wifi, WifiOff, ShieldCheck, ShieldAlert, ShieldOff } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { PanelSkeleton } from '../shared/LoadingSkeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CircuitBreakerState = 'closed' | 'open' | 'half-open';
type WebSocketStatus = 'connected' | 'disconnected' | 'reconnecting';

interface ApiLatency {
  name: string;
  latencyMs: number;
  status: 'ok' | 'degraded' | 'down';
}

interface SystemHealthData {
  apis: ApiLatency[];
  cacheHitRatio: number;
  wsStatus: WebSocketStatus;
  circuitBreaker: CircuitBreakerState;
  activeConnections: number;
  memoryUsageMb: number;
  memoryLimitMb: number;
  uptime: string;
  lastUpdated: number;
}

// ---------------------------------------------------------------------------
// Mock data generator
// ---------------------------------------------------------------------------

function generateHealthData(): SystemHealthData {
  const apis: ApiLatency[] = [
    { name: 'CoinGecko', latencyMs: Math.round(50 + Math.random() * 250), status: 'ok' },
    { name: 'Binance WS', latencyMs: Math.round(10 + Math.random() * 60), status: 'ok' },
    { name: 'Alpha Vantage', latencyMs: Math.round(100 + Math.random() * 500), status: 'ok' },
    { name: 'DeFi Llama', latencyMs: Math.round(80 + Math.random() * 300), status: 'ok' },
    { name: 'Finnhub', latencyMs: Math.round(60 + Math.random() * 200), status: 'ok' },
    { name: 'NewsAPI', latencyMs: Math.round(120 + Math.random() * 400), status: 'ok' },
  ];

  // Assign status based on latency
  for (const api of apis) {
    if (api.latencyMs > 500) api.status = 'down';
    else if (api.latencyMs > 200) api.status = 'degraded';
  }

  const wsRoll = Math.random();
  const wsStatus: WebSocketStatus = wsRoll > 0.15 ? 'connected' : wsRoll > 0.05 ? 'reconnecting' : 'disconnected';

  const cbRoll = Math.random();
  const circuitBreaker: CircuitBreakerState = cbRoll > 0.15 ? 'closed' : cbRoll > 0.05 ? 'half-open' : 'open';

  const hours = Math.floor(Math.random() * 72) + 1;
  const mins = Math.floor(Math.random() * 60);

  return {
    apis,
    cacheHitRatio: +(65 + Math.random() * 30).toFixed(1),
    wsStatus,
    circuitBreaker,
    activeConnections: Math.floor(2 + Math.random() * 8),
    memoryUsageMb: Math.round(120 + Math.random() * 180),
    memoryLimitMb: 512,
    uptime: `${hours}h ${mins}m`,
    lastUpdated: Date.now(),
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function latencyColor(ms: number): string {
  if (ms < 200) return 'var(--green)';
  if (ms < 500) return 'var(--amber)';
  return 'var(--red)';
}

function latencyLabel(ms: number): string {
  if (ms < 200) return 'Good';
  if (ms < 500) return 'Slow';
  return 'Down';
}

function wsStatusColor(status: WebSocketStatus): string {
  if (status === 'connected') return 'var(--green)';
  if (status === 'reconnecting') return 'var(--amber)';
  return 'var(--red)';
}

function cbColor(state: CircuitBreakerState): string {
  if (state === 'closed') return 'var(--green)';
  if (state === 'half-open') return 'var(--amber)';
  return 'var(--red)';
}

function cbLabel(state: CircuitBreakerState): string {
  if (state === 'closed') return 'Healthy';
  if (state === 'half-open') return 'Probing';
  return 'Tripped';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PanelSystemHealth = memo((): ReactElement => {
  const [data, setData] = useState<SystemHealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(() => {
    const health = generateHealthData();
    setData(health);
    setLastUpdated(health.lastUpdated);
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = setTimeout(loadData, 500);
    return () => clearTimeout(timer);
  }, [loadData]);

  // Refresh every 3 seconds
  useEffect(() => {
    intervalRef.current = setInterval(loadData, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [loadData]);

  if (loading || !data) {
    return (
      <PanelChrome title="System Health" icon={Activity} iconColor="var(--green)">
        <PanelSkeleton />
      </PanelChrome>
    );
  }

  const memPct = (data.memoryUsageMb / data.memoryLimitMb) * 100;
  const memColor = memPct < 60 ? 'var(--green)' : memPct < 85 ? 'var(--amber)' : 'var(--red)';

  const WsIcon = data.wsStatus === 'connected' ? Wifi : WifiOff;
  const CbIcon = data.circuitBreaker === 'closed' ? ShieldCheck : data.circuitBreaker === 'half-open' ? ShieldAlert : ShieldOff;

  return (
    <PanelChrome title="System Health" icon={Activity} iconColor="var(--green)" lastUpdated={lastUpdated}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%', minHeight: 0 }}>
        {/* Status overview cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
          {/* WebSocket */}
          <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '6px 8px', border: '1px solid var(--border-1)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
              <WsIcon size={10} color={wsStatusColor(data.wsStatus)} />
              <span style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>WebSocket</span>
            </div>
            <div style={{ fontSize: 10, fontWeight: 600, color: wsStatusColor(data.wsStatus), fontFamily: 'var(--font-mono)' }}>
              {data.wsStatus.toUpperCase()}
            </div>
          </div>

          {/* Circuit Breaker */}
          <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '6px 8px', border: '1px solid var(--border-1)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
              <CbIcon size={10} color={cbColor(data.circuitBreaker)} />
              <span style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase' }}>Circuit Brk</span>
            </div>
            <div style={{ fontSize: 10, fontWeight: 600, color: cbColor(data.circuitBreaker), fontFamily: 'var(--font-mono)' }}>
              {cbLabel(data.circuitBreaker)}
            </div>
          </div>

          {/* Connections */}
          <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '6px 8px', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: 4 }}>Connections</div>
            <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>
              {data.activeConnections}
            </div>
          </div>
        </div>

        {/* Cache & Memory row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {/* Cache hit ratio */}
          <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '6px 8px', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: 4 }}>Cache Hit Ratio</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: data.cacheHitRatio > 80 ? 'var(--green)' : 'var(--amber)' }}>
                {data.cacheHitRatio}%
              </span>
            </div>
            <div style={{ marginTop: 4, height: 3, background: 'var(--bg-3)', borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${data.cacheHitRatio}%`, background: data.cacheHitRatio > 80 ? 'var(--green)' : 'var(--amber)', borderRadius: 2, transition: 'width 0.3s ease' }} />
            </div>
          </div>

          {/* Memory */}
          <div style={{ background: 'var(--bg-1)', borderRadius: 6, padding: '6px 8px', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 8, color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: 4 }}>Memory</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: memColor }}>
                {data.memoryUsageMb}
              </span>
              <span style={{ fontSize: 9, color: 'var(--text-4)' }}>/ {data.memoryLimitMb} MB</span>
            </div>
            <div style={{ marginTop: 4, height: 3, background: 'var(--bg-3)', borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${memPct}%`, background: memColor, borderRadius: 2, transition: 'width 0.3s ease' }} />
            </div>
          </div>
        </div>

        {/* API latencies */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <div style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600, marginBottom: 4 }}>API Latencies</div>
          {data.apis.map((api) => (
            <div key={api.name} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 4px', borderBottom: '1px solid var(--border-1)', fontSize: 10 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: latencyColor(api.latencyMs), flexShrink: 0 }} />
              <span style={{ flex: 1, color: 'var(--text-2)' }}>{api.name}</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: latencyColor(api.latencyMs), fontWeight: 600, minWidth: 48, textAlign: 'right' }}>
                {api.latencyMs}ms
              </span>
              <span style={{ fontSize: 8, color: latencyColor(api.latencyMs), minWidth: 32, textAlign: 'right' }}>
                {latencyLabel(api.latencyMs)}
              </span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ fontSize: 9, color: 'var(--text-4)', display: 'flex', justifyContent: 'space-between' }}>
          <span>Uptime: {data.uptime}</span>
          <span>Updates every 3s</span>
        </div>
      </div>
    </PanelChrome>
  );
});
PanelSystemHealth.displayName = 'PanelSystemHealth';
export default PanelSystemHealth;
