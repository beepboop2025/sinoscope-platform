import { useReducedMotion } from 'framer-motion';
import type { Transition, Variants } from 'framer-motion';

// Spring presets
export const SPRING_DEFAULT: Transition = { type: 'spring', stiffness: 300, damping: 30 };
export const SPRING_BOUNCY: Transition = { type: 'spring', stiffness: 400, damping: 15 };
export const SPRING_GENTLE: Transition = { type: 'spring', stiffness: 200, damping: 25 };

// Panel mount/unmount variants
export const panelVariants: Variants = {
  hidden: { opacity: 0, scale: 0.96, y: 8 },
  visible: (staggerIndex: number = 0) => ({
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      ...SPRING_DEFAULT,
      delay: staggerIndex * 0.06,
    },
  }),
  exit: { opacity: 0, scale: 0.96, y: 8, transition: { duration: 0.15 } },
};

// List stagger variants
export const listContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.03,
    },
  },
};

export const listItemVariants: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: SPRING_GENTLE },
  exit: { opacity: 0, y: -6, transition: { duration: 0.1 } },
};

// Modal / overlay variants
export const overlayVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.15 } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
};

export const modalVariants: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: SPRING_DEFAULT },
  exit: { opacity: 0, scale: 0.95, transition: { duration: 0.1 } },
};

// Collapse/expand for panel body
export const collapseVariants: Variants = {
  open: { height: 'auto', opacity: 1, transition: { ...SPRING_GENTLE, opacity: { duration: 0.2 } } },
  closed: { height: 0, opacity: 0, overflow: 'hidden', transition: { duration: 0.2 } },
};

// Check reduced motion preference
export function reducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// Re-export framer-motion's hook
export { useReducedMotion };
