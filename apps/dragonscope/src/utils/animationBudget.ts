import { useState, useEffect, useRef } from 'react';

type Budget = 'full' | 'reduced' | 'minimal';

const FPS_SAMPLE_WINDOW = 60; // frames to average
const LOW_FPS_THRESHOLD = 30;
const LOW_FPS_DURATION_MS = 2000;

let currentBudget: Budget = 'full';
let listeners: Array<(b: Budget) => void> = [];

function notifyListeners(): void {
  for (const fn of listeners) fn(currentBudget);
}

/** Start monitoring FPS and auto-adjust animation budget. Call once on app mount. */
export function startAnimationBudgetMonitor(): () => void {
  const samples: number[] = [];
  let lastTime = performance.now();
  let lowSince: number | null = null;
  let raf: number;

  const tick = (): void => {
    const now = performance.now();
    const dt = now - lastTime;
    lastTime = now;

    if (dt > 0) {
      samples.push(1000 / dt);
      if (samples.length > FPS_SAMPLE_WINDOW) samples.shift();
    }

    if (samples.length >= 10) {
      const avgFps = samples.reduce((a, b) => a + b, 0) / samples.length;

      if (avgFps < LOW_FPS_THRESHOLD) {
        if (!lowSince) lowSince = now;
        const elapsed = now - lowSince;

        if (elapsed >= LOW_FPS_DURATION_MS && currentBudget === 'full') {
          currentBudget = 'reduced';
          notifyListeners();
        }
        if (elapsed >= LOW_FPS_DURATION_MS * 2 && currentBudget === 'reduced') {
          currentBudget = 'minimal';
          notifyListeners();
        }
      } else {
        lowSince = null;
        if (currentBudget !== 'full') {
          currentBudget = 'full';
          notifyListeners();
        }
      }
    }

    raf = requestAnimationFrame(tick);
  };

  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}

/** Get current animation budget */
export function getAnimationBudget(): Budget {
  return currentBudget;
}

/** React hook — re-renders when budget changes */
export function useAnimationBudget(): Budget {
  const [budget, setBudget] = useState<Budget>(currentBudget);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    const handler = (b: Budget): void => {
      if (mounted.current) setBudget(b);
    };
    listeners.push(handler);
    return () => {
      mounted.current = false;
      listeners = listeners.filter(l => l !== handler);
    };
  }, []);

  return budget;
}
