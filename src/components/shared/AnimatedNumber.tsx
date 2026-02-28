import { memo, useRef, useEffect, useState, type ReactElement } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { reducedMotion } from '../../utils/motion';

interface AnimatedNumberProps {
  value: number;
  format?: (v: number) => string;
  prefix?: string;
  suffix?: string;
  colorFlash?: boolean;
  className?: string;
}

const DIGIT_HEIGHT = 1.2; // em

function formatDefault(v: number): string {
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const AnimatedNumber = memo(({ value, format = formatDefault, prefix = '', suffix = '', colorFlash = false, className = '' }: AnimatedNumberProps): ReactElement => {
  const prevValue = useRef(value);
  const [direction, setDirection] = useState<'up' | 'down' | null>(null);
  const [glowClass, setGlowClass] = useState('');
  const noMotion = reducedMotion();

  useEffect(() => {
    if (value > prevValue.current) {
      setDirection('up');
      if (colorFlash) setGlowClass('text-glow-green');
    } else if (value < prevValue.current) {
      setDirection('down');
      if (colorFlash) setGlowClass('text-glow-red');
    }
    prevValue.current = value;

    if (colorFlash) {
      const timer = setTimeout(() => setGlowClass('text-glow-none'), 600);
      return () => clearTimeout(timer);
    }
  }, [value, colorFlash]);

  const formatted = `${prefix}${format(value)}${suffix}`;
  const chars = formatted.split('');

  if (noMotion) {
    return (
      <span className={`mono ${className} ${glowClass}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
        {formatted}
      </span>
    );
  }

  return (
    <span
      className={`mono ${className} ${glowClass}`}
      style={{ display: 'inline-flex', fontVariantNumeric: 'tabular-nums', overflow: 'hidden' }}
      aria-label={formatted}
    >
      {chars.map((char, i) => {
        const isDigit = /\d/.test(char);
        if (!isDigit) {
          return <span key={`sep-${i}`}>{char}</span>;
        }
        const yFrom = direction === 'up' ? DIGIT_HEIGHT : -DIGIT_HEIGHT;
        return (
          <span
            key={`pos-${i}`}
            style={{ display: 'inline-block', height: `${DIGIT_HEIGHT}em`, overflow: 'hidden', position: 'relative' }}
          >
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={`${char}-${i}-${value}`}
                initial={{ y: `${yFrom}em` }}
                animate={{ y: 0 }}
                exit={{ y: `${-yFrom}em` }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                style={{ display: 'inline-block', lineHeight: `${DIGIT_HEIGHT}em` }}
              >
                {char}
              </motion.span>
            </AnimatePresence>
          </span>
        );
      })}
    </span>
  );
});
AnimatedNumber.displayName = 'AnimatedNumber';
export default AnimatedNumber;
