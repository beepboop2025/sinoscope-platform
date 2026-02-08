import { memo, useState, useRef, useCallback, useEffect } from 'react';
import { Minus, Maximize2, X, Download } from 'lucide-react';
import { exportChartAsPng } from '../../utils/export';

function formatTimeAgo(ts) {
  if (!ts) return null;
  const secs = Math.round((Date.now() - ts) / 1000);
  if (secs < 10) return 'just now';
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const PanelChrome = memo(({ title, icon: Icon, iconColor = 'var(--text-3)', children, onClose, className = '', exportable = false, lastUpdated }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [timeAgo, setTimeAgo] = useState(() => formatTimeAgo(lastUpdated));
  const bodyRef = useRef(null);

  useEffect(() => {
    if (!lastUpdated) { setTimeAgo(null); return; }
    setTimeAgo(formatTimeAgo(lastUpdated));
    const id = setInterval(() => setTimeAgo(formatTimeAgo(lastUpdated)), 15000);
    return () => clearInterval(id);
  }, [lastUpdated]);

  const handleExport = useCallback(() => {
    if (!bodyRef.current) return;
    const safeName = (title || 'chart').replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    exportChartAsPng(bodyRef.current, `${safeName}.png`);
  }, [title]);

  return (
    <div className={`panel ${className}`} role="region" aria-label={title}>
      <div className="panel-titlebar">
        {Icon && <Icon size={12} color={iconColor} aria-hidden="true" />}
        <span className="panel-title">{title}</span>
        {timeAgo && (
          <span style={{ fontSize: 8, color: 'var(--text-4)', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap', flexShrink: 0 }}>
            {timeAgo}
          </span>
        )}
        {exportable && (
          <button className="panel-btn" onClick={handleExport} title="Export as PNG" aria-label={`Export ${title} as PNG`}>
            <Download size={10} aria-hidden="true" />
          </button>
        )}
        <button
          className="panel-btn"
          onClick={() => setCollapsed(c => !c)}
          title={collapsed ? 'Expand' : 'Collapse'}
          aria-label={collapsed ? `Expand ${title} panel` : `Collapse ${title} panel`}
        >
          {collapsed ? <Maximize2 size={10} aria-hidden="true" /> : <Minus size={10} aria-hidden="true" />}
        </button>
        {onClose && (
          <button className="panel-btn" onClick={onClose} aria-label={`Close ${title} panel`}>
            <X size={10} aria-hidden="true" />
          </button>
        )}
      </div>
      {!collapsed && (
        <div className="panel-body" ref={bodyRef}>
          {children}
        </div>
      )}
    </div>
  );
});
PanelChrome.displayName = "PanelChrome";
export default PanelChrome;
