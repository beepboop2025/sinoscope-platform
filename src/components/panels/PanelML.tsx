import { memo, useMemo, type ReactElement } from 'react';
import { Brain, RefreshCw, RotateCcw, TrendingUp, TrendingDown, AlertTriangle, Activity } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';

interface TrainingStatus {
  epochs?: number;
  dataPoints?: number;
  priceAccuracy?: number;
  regimeAccuracy?: number;
  priceLoss?: number;
  isTraining?: boolean;
  lastTrained?: number;
}

interface Anomaly {
  symbol: string;
  severity: string;
  direction: string;
  changePct: number;
  zScore: number;
}

interface SignalSummary {
  total: number;
  buys: number;
  holds: number;
  sells: number;
  avgScore: number;
  strongBuys?: string[];
  strongSells?: string[];
}

interface MLState {
  trainingStatus?: TrainingStatus;
  signalSummary?: SignalSummary;
  anomalies?: Anomaly[];
  trackedSymbols?: number;
  dataPoints?: number;
  trainLoss?: number[];
}

interface PanelMLProps {
  mlState?: MLState;
  onRetrain?: () => void;
  onReset?: () => void;
}

interface StatProps {
  label: string;
  value: number | string;
}

interface MeterBarProps {
  label: string;
  value: number;
  color: string;
}

const PanelML = memo(function PanelML({ mlState, onRetrain, onReset }: PanelMLProps): ReactElement {
  const { trainingStatus, signalSummary, anomalies, trackedSymbols, dataPoints, trainLoss } = mlState || {};

  const lossChart = useMemo(() => {
    if (!trainLoss || trainLoss.length < 2) return null;
    const maxLoss = Math.max(...trainLoss, 0.01);
    const w = 200;
    const h = 50;
    const points = trainLoss.map((l, i) => {
      const x = (i / (trainLoss.length - 1)) * w;
      const y = h - (l / maxLoss) * h;
      return `${x},${y}`;
    }).join(' ');
    return (
      <svg width={w} height={h} style={{ display: 'block' }}>
        <polyline points={points} fill="none" stroke="var(--cyan)" strokeWidth="1.5" />
      </svg>
    );
  }, [trainLoss]);

  const status = trainingStatus || {} as TrainingStatus;

  return (
    <PanelChrome title="ML Dashboard" icon={Brain} iconColor="var(--magenta)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%', minHeight: 0, overflow: 'auto', padding: '0 2px' }}>

        {/* Training Status */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <Stat label="Symbols" value={trackedSymbols || 0} />
          <Stat label="Data Points" value={dataPoints || 0} />
          <Stat label="Epochs" value={status.epochs || 0} />
          <Stat label="Samples" value={status.dataPoints || 0} />
        </div>

        {/* Accuracy Meters */}
        <div style={{ display: 'flex', gap: 8 }}>
          <MeterBar label="Price Accuracy" value={status.priceAccuracy || 0} color="var(--green)" />
          <MeterBar label="Regime Accuracy" value={status.regimeAccuracy || 0} color="var(--cyan)" />
        </div>

        {/* Loss Chart */}
        <div>
          <div style={{ fontSize: 9, color: 'var(--text-3)', marginBottom: 2 }}>Training Loss</div>
          {lossChart || <div style={{ fontSize: 9, color: 'var(--text-3)' }}>Collecting data...</div>}
          {(status.priceLoss || 0) < 1 && (
            <div style={{ fontSize: 9, color: 'var(--text-3)' }}>Current: {(Number(status.priceLoss) || 0).toFixed(4)}</div>
          )}
        </div>

        {/* Signal Summary */}
        {signalSummary && signalSummary.total > 0 && (
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-3)', marginBottom: 3 }}>Signal Summary</div>
            <div style={{ display: 'flex', gap: 6, fontSize: 10 }}>
              <span style={{ color: 'var(--green)' }}><TrendingUp size={10} /> {signalSummary.buys} Buy</span>
              <span style={{ color: 'var(--text-2)' }}>{signalSummary.holds} Hold</span>
              <span style={{ color: 'var(--red)' }}><TrendingDown size={10} /> {signalSummary.sells} Sell</span>
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-3)', marginTop: 2 }}>
              Market Score: <span style={{ color: signalSummary.avgScore > 10 ? 'var(--green)' : signalSummary.avgScore < -10 ? 'var(--red)' : 'var(--text-2)' }}>
                {signalSummary.avgScore > 0 ? '+' : ''}{signalSummary.avgScore}
              </span>
            </div>
            {signalSummary.strongBuys && signalSummary.strongBuys.length > 0 && (
              <div style={{ fontSize: 9, color: 'var(--green)', marginTop: 2 }}>
                Strong Buy: {signalSummary.strongBuys.join(', ')}
              </div>
            )}
            {signalSummary.strongSells && signalSummary.strongSells.length > 0 && (
              <div style={{ fontSize: 9, color: 'var(--red)', marginTop: 1 }}>
                Strong Sell: {signalSummary.strongSells.join(', ')}
              </div>
            )}
          </div>
        )}

        {/* Anomalies */}
        {anomalies && anomalies.length > 0 && (
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-3)', marginBottom: 3, display: 'flex', alignItems: 'center', gap: 3 }}>
              <AlertTriangle size={10} /> Recent Anomalies
            </div>
            {anomalies.slice(0, 5).map((a, i) => (
              <div key={i} style={{ fontSize: 9, display: 'flex', gap: 4, alignItems: 'center', marginBottom: 1 }}>
                <span style={{
                  color: a.severity === 'critical' ? 'var(--red)' : a.severity === 'high' ? 'var(--amber)' : 'var(--text-2)',
                  fontWeight: a.severity === 'critical' ? 600 : 400,
                }}>
                  {a.symbol}
                </span>
                <span style={{ color: a.direction === 'spike' ? 'var(--green)' : 'var(--red)' }}>
                  {a.direction === 'spike' ? '+' : ''}{(Number(a.changePct) || 0).toFixed(2)}%
                </span>
                <span style={{ color: 'var(--text-3)' }}>z={(Number(a.zScore) || 0).toFixed(1)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Training Status */}
        <div style={{ fontSize: 9, color: status.isTraining ? 'var(--amber)' : 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 3 }}>
          <Activity size={10} />
          {status.isTraining ? 'Training...' :
            status.lastTrained ? `Last trained ${Math.round((Date.now() - status.lastTrained) / 1000)}s ago` :
            'Waiting for data...'}
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', gap: 4, marginTop: 'auto' }}>
          <button className="btn-ghost" onClick={onRetrain} style={{ fontSize: 9, padding: '2px 8px', display: 'flex', alignItems: 'center', gap: 3 }}>
            <RefreshCw size={10} /> Retrain
          </button>
          <button className="btn-ghost" onClick={onReset} style={{ fontSize: 9, padding: '2px 8px', display: 'flex', alignItems: 'center', gap: 3 }}>
            <RotateCcw size={10} /> Reset
          </button>
        </div>
      </div>
    </PanelChrome>
  );
});

function Stat({ label, value }: StatProps): ReactElement {
  return (
    <div style={{ background: 'var(--bg-2)', borderRadius: 4, padding: '3px 6px', minWidth: 50 }}>
      <div style={{ fontSize: 8, color: 'var(--text-3)', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>{value}</div>
    </div>
  );
}

function MeterBar({ label, value, color }: MeterBarProps): ReactElement {
  const pct = Math.round((Number(value) || 0) * 100);
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--text-3)', marginBottom: 2 }}>
        <span>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{pct}%</span>
      </div>
      <div style={{ background: 'var(--bg-3)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
        <div style={{ background: color, height: '100%', width: `${pct}%`, borderRadius: 3, transition: 'width 0.5s ease' }} />
      </div>
    </div>
  );
}

PanelML.displayName = 'PanelML';
export default PanelML;
