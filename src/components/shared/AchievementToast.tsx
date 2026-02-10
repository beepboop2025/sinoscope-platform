import { memo, useEffect, type ReactElement } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import confetti from 'canvas-confetti';
import { playSound } from '../../utils/audio';
import type { Achievement } from '../../constants/achievements';

interface AchievementToastProps {
  achievement: Achievement | null;
  onDone: () => void;
}

const DISPLAY_MS = 4000;

const AchievementToast = memo<AchievementToastProps>(({ achievement, onDone }): ReactElement => {
  useEffect(() => {
    if (!achievement) return;

    // Confetti burst — 30 particles max, centered
    try {
      confetti({
        particleCount: 30,
        spread: 60,
        origin: { x: 0.5, y: 0.35 },
        colors: ['#00DC82', '#3B82F6', '#8B5CF6', '#F59E0B', '#FFD700'],
        disableForReducedMotion: true,
      });
    } catch {
      // canvas-confetti may not be available in SSR / test
    }

    playSound('achievement');

    const timer = setTimeout(onDone, DISPLAY_MS);
    return () => clearTimeout(timer);
  }, [achievement, onDone]);

  return (
    <AnimatePresence>
      {achievement && (
        <motion.div
          key={achievement.id}
          role="alert"
          aria-live="assertive"
          initial={{ opacity: 0, y: 40, scale: 0.85 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.9 }}
          transition={{
            type: 'spring',
            stiffness: 400,
            damping: 20,
          }}
          style={{
            position: 'fixed',
            top: '18%',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
            padding: '20px 32px',
            background: 'var(--glass-bg-heavy, rgba(20,20,30,0.92))',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid var(--glass-border, rgba(255,255,255,0.08))',
            borderRadius: 'var(--radius-xl, 16px)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.5), 0 0 60px rgba(139,92,246,0.15)',
            pointerEvents: 'auto',
          }}
        >
          <span style={{ fontSize: 36, lineHeight: 1 }}>{achievement.icon}</span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--purple, #8B5CF6)',
            }}
          >
            Achievement Unlocked
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: 'var(--text-1)',
              textAlign: 'center',
            }}
          >
            {achievement.name}
          </span>
          <span
            style={{
              fontSize: 11,
              color: 'var(--text-3)',
              textAlign: 'center',
              maxWidth: 240,
            }}
          >
            {achievement.description}
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: 'var(--amber, #F59E0B)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            +{achievement.xpReward} XP
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
});
AchievementToast.displayName = 'AchievementToast';
export default AchievementToast;
