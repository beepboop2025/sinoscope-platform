import { memo, type ReactElement } from 'react';
import { useGamification } from '../../stores/gamification';

const LEVEL_COLORS = [
  'var(--text-3)',    // 1
  'var(--green)',     // 2
  'var(--blue)',      // 3
  'var(--purple)',    // 4
  'var(--amber)',     // 5
  'var(--cyan)',      // 6
  'var(--orange)',    // 7
  'var(--pink)',      // 8
  'var(--red)',       // 9
  '#FFD700',         // 10 (gold)
];

const LevelBadge = memo((): ReactElement => {
  const level = useGamification(s => s.level);
  const color = LEVEL_COLORS[Math.min(level - 1, LEVEL_COLORS.length - 1)];

  return (
    <div
      title={`Level ${level}`}
      style={{
        width: 20,
        height: 20,
        borderRadius: '50%',
        background: `${color}20`,
        border: `1.5px solid ${color}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 9,
        fontWeight: 700,
        color,
        fontFamily: 'var(--font-mono)',
      }}
    >
      {level}
    </div>
  );
});
LevelBadge.displayName = 'LevelBadge';
export default LevelBadge;
