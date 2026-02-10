import { memo, useState, Fragment, type ReactElement } from 'react';
import { Grid3X3 } from 'lucide-react';
import PanelChrome from '../shared/PanelChrome';
import { correlationColor } from '../../constants/colors';

interface PanelCorrelationProps {
  matrix?: Record<string, Record<string, number>>;
  symbols?: string[];
  window?: number;
  onWindowChange?: (w: number) => void;
}

const PanelCorrelation = memo(({ matrix, symbols = [], window: windowProp = 30, onWindowChange }: PanelCorrelationProps): ReactElement => {
  const [window, setWindow] = useState<number>(windowProp);

  const handleWindowChange = (w: number): void => {
    setWindow(w);
    onWindowChange?.(w);
  };

  if (!matrix || symbols.length === 0) {
    return (
      <PanelChrome title="Correlation Matrix" icon={Grid3X3} iconColor="var(--teal)">
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
          Collecting data for correlation analysis...
        </div>
      </PanelChrome>
    );
  }

  return (
    <PanelChrome title="Cross-Market Correlation" icon={Grid3X3} iconColor="var(--teal)">
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {[7, 30, 90].map(w => (
          <button key={w} className={`tab-btn ${window === w ? 'active' : ''}`} onClick={() => handleWindowChange(w)} style={{ padding: '2px 8px', fontSize: 10 }}>
            {w}D
          </button>
        ))}
      </div>
      <div style={{ overflowX: 'auto' }}>
        <div className="heatmap-grid" style={{ gridTemplateColumns: `40px repeat(${symbols.length}, 1fr)` }}>
          <div />
          {symbols.map(s => (
            <div key={s} style={{ fontSize: 8, textAlign: 'center', color: 'var(--text-3)', padding: '2px 0', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s}</div>
          ))}
          {symbols.map(s1 => (
            <Fragment key={s1}>
              <div style={{ fontSize: 8, display: 'flex', alignItems: 'center', color: 'var(--text-3)', paddingRight: 4, justifyContent: 'flex-end' }}>{s1}</div>
              {symbols.map(s2 => {
                const val = matrix[s1]?.[s2] ?? 0;
                return (
                  <div
                    key={`${s1}_${s2}`}
                    className="heatmap-cell"
                    style={{ background: correlationColor(val), color: Math.abs(val) > 0.4 ? '#fff' : 'var(--text-2)' }}
                    title={`${s1} vs ${s2}: ${val.toFixed(2)}`}
                  >
                    {val.toFixed(1)}
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </PanelChrome>
  );
});
PanelCorrelation.displayName = "PanelCorrelation";
export default PanelCorrelation;
