import { memo } from 'react';
const HeatmapCell = memo(({ value, label, color, size = 32 }) => (
  <div
    className="heatmap-cell"
    style={{ background: color, minHeight: size, color: Math.abs(value) > 0.5 ? '#fff' : 'var(--text-2)' }}
    title={`${label || ''}: ${(Number(value) || 0).toFixed(2)}`}
  >
    {(Number(value) || 0).toFixed(2)}
  </div>
));
HeatmapCell.displayName = "HeatmapCell";
export default HeatmapCell;
