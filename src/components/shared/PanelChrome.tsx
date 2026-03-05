import { memo, useState, useRef, useCallback, useEffect, type ReactElement, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Minus, Maximize2, X, Download, Link } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { exportChartAsPng } from '../../utils/export';
import { panelVariants, collapseVariants, reducedMotion } from '../../utils/motion';

function formatTimeAgo(ts: number | null | undefined): string | null {
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

function freshnessColor(ts: number | null | undefined): string {
  if (!ts) return 'var(--text-4)';
  const secs = Math.round((Date.now() - ts) / 1000);
  if (secs < 10) return 'var(--green)';
  if (secs < 60) return 'var(--amber)';
  return 'var(--red)';
}

function freshnessStatus(ts: number | null | undefined): string {
  if (!ts) return 'stale';
  const secs = Math.round((Date.now() - ts) / 1000);
  if (secs < 10) return 'live';
  if (secs < 60) return 'loading';
  return 'error';
}

export interface PanelChromeProps {
  title: string;
  icon?: LucideIcon | React.ComponentType<{ size?: number; color?: string }>;
  iconColor?: string;
  children: ReactNode;
  onClose?: () => void;
  className?: string;
  exportable?: boolean;
  lastUpdated?: number | null;
  staggerIndex?: number;
  linked?: boolean;
  onToggleLink?: () => void;
  subtitle?: string;
  panelId?: string;
}

const PanelChrome = memo(({
  title,
  icon: Icon,
  iconColor = 'var(--text-3)',
  children,
  onClose,
  className = '',
  exportable = false,
  lastUpdated,
  staggerIndex = 0,
  linked = false,
  onToggleLink,
}: PanelChromeProps): ReactElement => {
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [timeAgo, setTimeAgo] = useState<string | null>(() => formatTimeAgo(lastUpdated));
  const bodyRef = useRef<HTMLDivElement>(null);
  const noMotion = reducedMotion();

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

  const heartbeatStatus = freshnessStatus(lastUpdated);
  const dotColor = freshnessColor(lastUpdated);

  const content = (
    <div className={`panel ${className}`} role="region" aria-label={title}>
      <div className="panel-titlebar">
        {Icon && <Icon size={12} color={iconColor} aria-hidden="true" />}
        <span className="panel-title">{title}</span>

        {/* Data freshness heartbeat */}
        {lastUpdated && (
          <div
            className={`status-heartbeat ${heartbeatStatus}`}
            title={timeAgo || undefined}
            aria-hidden="true"
          />
        )}

        {timeAgo && (
          <span style={{ fontSize: 8, color: dotColor, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap', flexShrink: 0 }}>
            {timeAgo}
          </span>
        )}

        {/* Link toggle for SymbolContext */}
        {onToggleLink && (
          <button
            className="panel-btn"
            onClick={onToggleLink}
            title={linked ? 'Unlink from active symbol' : 'Link to active symbol'}
            aria-label={linked ? 'Unlink panel' : 'Link panel'}
          >
            <Link size={10} color={linked ? 'var(--blue)' : 'var(--text-4)'} aria-hidden="true" />
          </button>
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

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            key="panel-body"
            variants={noMotion ? undefined : collapseVariants}
            initial={noMotion ? undefined : 'closed'}
            animate={noMotion ? undefined : 'open'}
            exit={noMotion ? undefined : 'closed'}
            className="panel-body"
            ref={bodyRef}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );

  // Wrap with motion for stagger animation on mount
  if (noMotion) return content;

  return (
    <motion.div
      variants={panelVariants}
      initial="hidden"
      animate="visible"
      custom={staggerIndex}
      style={{ height: '100%' }}
    >
      {content}
    </motion.div>
  );
});
PanelChrome.displayName = "PanelChrome";
export default PanelChrome;
