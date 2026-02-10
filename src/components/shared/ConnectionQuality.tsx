import { memo, type ReactElement } from 'react';
import { motion } from 'framer-motion';

type Quality = 'excellent' | 'good' | 'fair' | 'poor' | 'disconnected';

interface ConnectionQualityProps {
  /** WebSocket latency in ms, or -1 for disconnected */
  latency: number;
}

function getQuality(latency: number): Quality {
  if (latency < 0) return 'disconnected';
  if (latency < 100) return 'excellent';
  if (latency < 300) return 'good';
  if (latency < 800) return 'fair';
  return 'poor';
}

const QUALITY_COLORS: Record<Quality, string> = {
  excellent: 'var(--green, #00DC82)',
  good: 'var(--green, #00DC82)',
  fair: 'var(--amber, #F59E0B)',
  poor: 'var(--red, #FF4458)',
  disconnected: 'var(--text-4, #555)',
};

const QUALITY_BARS: Record<Quality, number> = {
  excellent: 4,
  good: 3,
  fair: 2,
  poor: 1,
  disconnected: 0,
};

const ConnectionQuality = memo<ConnectionQualityProps>(({ latency }): ReactElement => {
  const quality = getQuality(latency);
  const activeBars = QUALITY_BARS[quality];
  const color = QUALITY_COLORS[quality];
  const label = latency >= 0 ? `${latency}ms` : 'offline';

  return (
    <div
      title={`Connection: ${quality} (${label})`}
      aria-label={`Connection quality: ${quality}, latency ${label}`}
      role="status"
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 1.5,
        height: 16,
      }}
    >
      {[1, 2, 3, 4].map(bar => {
        const barHeight = 4 + bar * 3; // 7, 10, 13, 16
        const isActive = bar <= activeBars;
        return (
          <motion.div
            key={bar}
            initial={false}
            animate={{
              backgroundColor: isActive ? color : 'var(--surface-3, rgba(255,255,255,0.09))',
              opacity: isActive ? 1 : 0.4,
            }}
            transition={{ duration: 0.3 }}
            style={{
              width: 3,
              height: barHeight,
              borderRadius: 1,
            }}
          />
        );
      })}
    </div>
  );
});
ConnectionQuality.displayName = 'ConnectionQuality';
export default ConnectionQuality;
