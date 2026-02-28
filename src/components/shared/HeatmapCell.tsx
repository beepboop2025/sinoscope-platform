import { memo, type ReactElement } from 'react';

interface HeatmapCellProps {
  value: number;
  label?: string;
  color: string;
  size?: number;
}

const HeatmapCell = memo(({ value, label, color, size = 32 }: HeatmapCellProps): ReactElement => (
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
