import { useState, useRef, useEffect, useCallback } from 'react';

export function useThrottledUpdate(sourceRef, intervalMs = 1000) {
  const [display, setDisplay] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    timer.current = setInterval(() => {
      if (sourceRef.current) {
        setDisplay({ ...sourceRef.current });
      }
    }, intervalMs);

    return () => clearInterval(timer.current);
  }, [sourceRef, intervalMs]);

  return display;
}

export function useThrottledCallback(callback, intervalMs = 1000) {
  const lastCall = useRef(0);

  return useCallback((...args) => {
    const now = Date.now();
    if (now - lastCall.current >= intervalMs) {
      lastCall.current = now;
      callback(...args);
    }
  }, [callback, intervalMs]);
}
