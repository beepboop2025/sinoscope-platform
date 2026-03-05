import { useState, memo, type ReactElement } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Layout, Keyboard, TrendingUp, Brain, Database, ChevronRight, ChevronLeft, X } from 'lucide-react';

const STORAGE_KEY = 'dragonscope-onboarded';

interface StepConfig {
  icon: typeof Activity;
  iconColor: string;
  title: string;
  description: string;
  features: string[];
}

const STEPS: StepConfig[] = [
  {
    icon: Activity,
    iconColor: 'var(--cyan)',
    title: 'Welcome to DragonScope',
    description: 'Your real-time financial analytics terminal. Track markets, analyze data, and discover insights across 45+ panels.',
    features: [
      'Real-time data from 17+ APIs with WebSocket streaming',
      'In-browser ML with neural network predictions',
      'Professional candlestick charts and correlation analysis',
    ],
  },
  {
    icon: Layout,
    iconColor: 'var(--purple)',
    title: '9 Workspaces, Infinite Layouts',
    description: 'Switch between pre-configured workspaces or build your own. Every panel is draggable and resizable.',
    features: [
      'Press 1-9 to instantly switch workspaces',
      'Drag panels by their title bar to rearrange',
      'Add any panel via the command bar (Ctrl+K)',
    ],
  },
  {
    icon: Keyboard,
    iconColor: 'var(--green)',
    title: 'Power User Shortcuts',
    description: 'DragonScope is built for speed. Master these shortcuts to navigate like a pro.',
    features: [
      'Ctrl+K — Open command bar to search & navigate',
      '1-9 — Switch between workspaces instantly',
      'Ctrl+? — View all keyboard shortcuts',
    ],
  },
];

const WelcomeModal = memo((): ReactElement | null => {
  const [visible, setVisible] = useState(() => {
    try {
      return !localStorage.getItem(STORAGE_KEY);
    } catch {
      return false;
    }
  });
  const [step, setStep] = useState(0);

  const handleDismiss = () => {
    setVisible(false);
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch { /* localStorage unavailable */ }
  };

  const handleNext = () => {
    if (step < STEPS.length - 1) {
      setStep(s => s + 1);
    } else {
      handleDismiss();
    }
  };

  const handlePrev = () => {
    if (step > 0) setStep(s => s - 1);
  };

  if (!visible) return null;

  const current = STEPS[step];
  const Icon = current.icon;
  const isLast = step === STEPS.length - 1;

  const FEATURE_ICONS = [TrendingUp, Brain, Database];

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(5, 8, 16, 0.70)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
          }}
          onClick={handleDismiss}
        >
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.96 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--glass-bg-heavy)',
              border: '1px solid var(--border-2)',
              borderRadius: 'var(--radius-2xl)',
              padding: 32,
              maxWidth: 480,
              width: '90vw',
              position: 'relative',
              boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
            }}
          >
            {/* Close button */}
            <button
              onClick={handleDismiss}
              aria-label="Close welcome modal"
              style={{
                position: 'absolute',
                top: 12,
                right: 12,
                background: 'none',
                border: 'none',
                color: 'var(--text-4)',
                cursor: 'pointer',
                padding: 4,
                display: 'flex',
              }}
            >
              <X size={16} />
            </button>

            {/* Icon */}
            <div style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              background: `${current.iconColor}15`,
              border: `1px solid ${current.iconColor}30`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}>
              <Icon size={22} color={current.iconColor} />
            </div>

            {/* Title */}
            <h2 style={{
              fontSize: 20,
              fontWeight: 700,
              color: 'var(--text-0)',
              marginBottom: 8,
              fontFamily: 'var(--font-sans)',
            }}>
              {current.title}
            </h2>

            {/* Description */}
            <p style={{
              fontSize: 13,
              color: 'var(--text-2)',
              lineHeight: 1.5,
              marginBottom: 20,
            }}>
              {current.description}
            </p>

            {/* Features */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
              {current.features.map((feat, i) => {
                const FeatIcon = FEATURE_ICONS[i] || TrendingUp;
                return (
                  <div key={i} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '8px 12px',
                    background: 'var(--surface-1)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-1)',
                  }}>
                    <FeatIcon size={14} color={current.iconColor} style={{ marginTop: 1, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: 'var(--text-1)', lineHeight: 1.4 }}>{feat}</span>
                  </div>
                );
              })}
            </div>

            {/* Step indicators */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, marginBottom: 20 }}>
              {STEPS.map((_, i) => (
                <div
                  key={i}
                  style={{
                    width: i === step ? 20 : 6,
                    height: 6,
                    borderRadius: 3,
                    background: i === step ? 'var(--cyan)' : 'var(--surface-3)',
                    transition: 'all 0.2s ease',
                  }}
                />
              ))}
            </div>

            {/* Navigation buttons */}
            <div style={{ display: 'flex', gap: 8 }}>
              {step > 0 && (
                <button
                  onClick={handlePrev}
                  className="btn-ghost"
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  <ChevronLeft size={14} />
                  Back
                </button>
              )}
              <button
                onClick={handleNext}
                className="btn-primary"
                style={{ flex: 1, justifyContent: 'center' }}
              >
                {isLast ? 'Get Started' : 'Next'}
                {!isLast && <ChevronRight size={14} />}
              </button>
            </div>

            {/* Skip */}
            {!isLast && (
              <button
                onClick={handleDismiss}
                style={{
                  display: 'block',
                  margin: '12px auto 0',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-4)',
                  fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                Skip tutorial
              </button>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
});
WelcomeModal.displayName = "WelcomeModal";
export default WelcomeModal;
