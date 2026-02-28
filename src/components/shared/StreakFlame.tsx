import { memo, type ReactElement } from 'react';
import { motion } from 'framer-motion';
import { useGamification } from '../../stores/gamification';

const StreakFlame = memo((): ReactElement => {
  const streak = useGamification(s => s.streak);

  if (streak < 1) {
    return <></>;
  }

  return (
    <div
      title={`${streak}-day streak`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 3,
        fontSize: 11,
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        color: streak >= 7 ? 'var(--amber, #F59E0B)' : 'var(--text-2)',
      }}
    >
      <motion.span
        aria-hidden="true"
        animate={{
          scale: [1, 1.15, 1],
          rotate: [0, -5, 5, 0],
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity,
          repeatType: 'loop',
          ease: 'easeInOut',
        }}
        style={{
          display: 'inline-block',
          fontSize: 14,
          lineHeight: 1,
          filter: streak >= 7 ? 'drop-shadow(0 0 4px rgba(245,158,11,0.5))' : 'none',
        }}
      >
        {streak >= 30 ? '\uD83D\uDC8E' : '\uD83D\uDD25'}
      </motion.span>
      {streak}
    </div>
  );
});
StreakFlame.displayName = 'StreakFlame';
export default StreakFlame;
