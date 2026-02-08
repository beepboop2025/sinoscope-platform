import { memo, useState, useCallback } from 'react';
import { correlationColor } from '../../constants/colors';

const HeatmapGrid = memo(({ matrix = {}, symbols = [], cellSize = 36, showValues = true, colorFn = correlationColor, onCellClick }) => {
  const [selectedCell, setSelectedCell] = useState(null);

  const handleCellClick = useCallback((row, col, val) => {
    const key = `${row}_${col}`;
    setSelectedCell(prev => prev === key ? null : key);
    if (onCellClick) onCellClick({ row, col, value: val });
  }, [onCellClick]);

  if (symbols.length === 0) return null;

  return (
    <div style={{ overflowX: 'auto', position: 'relative' }}>
      <div
        className="heatmap-grid"
        style={{ gridTemplateColumns: `40px repeat(${symbols.length}, ${cellSize}px)`, gap: 1 }}
      >
        <div />
        {symbols.map(s => (
          <div key={s} style={{ fontSize: 8, textAlign: 'center', color: 'var(--text-3)', padding: '2px 0', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {s.slice(0, 5)}
          </div>
        ))}
        {symbols.map(row => (
          <div key={row} style={{ display: 'contents' }}>
            <div style={{ fontSize: 8, display: 'flex', alignItems: 'center', color: 'var(--text-3)', paddingRight: 4, justifyContent: 'flex-end' }}>
              {row.slice(0, 5)}
            </div>
            {symbols.map(col => {
              const val = matrix[row]?.[col] ?? 0;
              const cellKey = `${row}_${col}`;
              const isSelected = selectedCell === cellKey;
              return (
                <div
                  key={cellKey}
                  className="heatmap-cell"
                  style={{
                    background: colorFn(val),
                    color: Math.abs(val) > 0.4 ? '#fff' : 'var(--text-2)',
                    width: cellSize,
                    height: cellSize,
                    cursor: 'pointer',
                    outline: isSelected ? '2px solid var(--cyan)' : 'none',
                    outlineOffset: -1,
                    position: 'relative',
                    zIndex: isSelected ? 2 : 1,
                  }}
                  title={`${row} vs ${col}: ${val.toFixed(3)}`}
                  onClick={() => handleCellClick(row, col, val)}
                >
                  {isSelected ? val.toFixed(3) : (showValues ? val.toFixed(1) : '')}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
});
HeatmapGrid.displayName = 'HeatmapGrid';
export default HeatmapGrid;
