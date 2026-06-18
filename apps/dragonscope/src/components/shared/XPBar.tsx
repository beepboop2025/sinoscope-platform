import { memo, type ReactElement } from 'react';
import { motion } from 'framer-motion';
import { useGamification } from '../../stores/gamification';
import { getXPForNextLevel } from '../../constants/xpActions';

const XPBar = memo((): ReactElement => {
  const xp = useGamification(s => s.xp);
  const level = useGamification(s => s.level);
  const { progress } = getXPForNextLevel(xp);

  const size = 24;
  const strokeWidth = 2.5;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <div style={{ position: 'relative', width: size, height: size }} title={`Level ${level} — ${xp} XP`}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={strokeWidth}
        />
        {/* Progress ring */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--cyan)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - progress) }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </svg>
      <span style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 8, fontWeight: 700, color: 'var(--text-1)',
        fontFamily: 'var(--font-mono)',
      }}>
        {level}
      </span>
    </div>
  );
});
XPBar.displayName = 'XPBar';
export default XPBar;
