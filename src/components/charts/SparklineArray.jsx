import { memo } from 'react';
import MiniSparkline from '../shared/MiniSparkline';

const SparklineArray = memo(({ items = [], height = 30, width = 80 }) => {
  if (!items.length) return null;

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      {items.map(item => (
        <div key={item.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <MiniSparkline data={item.data} width={width} height={height} color={item.color || 'var(--cyan)'} />
          <span style={{ fontSize: 9, color: 'var(--text-3)' }}>{item.label}</span>
          {item.value != null && (
            <span style={{ fontSize: 10, color: 'var(--text-1)', fontWeight: 500 }}>{item.value}</span>
          )}
        </div>
      ))}
    </div>
  );
});
SparklineArray.displayName = 'SparklineArray';
export default SparklineArray;
