/**
 * useVisibility — IntersectionObserver hook for lazy panel data fetching.
 *
 * Usage:
 *   const { ref, isVisible } = useVisibility<HTMLDivElement>();
 *   // Only fetch data when isVisible is true
 *   useEffect(() => { if (isVisible) fetchData(); }, [isVisible]);
 *
 * The hook remembers if the element was EVER visible (sticky = true by default)
 * so data fetched once is not lost when the panel scrolls out of view.
 */

import { useRef, useState, useEffect, useCallback, type RefObject } from 'react';

interface UseVisibilityOptions {
  /** Root margin for IntersectionObserver (default: "100px" — trigger 100px before visible) */
  rootMargin?: string;
  /** Minimum intersection ratio to count as visible (default: 0) */
  threshold?: number;
  /** If true, once visible the hook stays true forever (default: true) */
  sticky?: boolean;
}

interface UseVisibilityReturn<T extends HTMLElement> {
  ref: RefObject<T | null>;
  isVisible: boolean;
  /** Whether the element has EVER been visible */
  hasBeenVisible: boolean;
}

export function useVisibility<T extends HTMLElement = HTMLDivElement>(
  options: UseVisibilityOptions = {}
): UseVisibilityReturn<T> {
  const { rootMargin = '100px', threshold = 0, sticky = true } = options;
  const ref = useRef<T | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [hasBeenVisible, setHasBeenVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    // If already sticky-visible, no need to observe further
    if (sticky && hasBeenVisible) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        const visible = entry.isIntersecting;
        setIsVisible(visible);
        if (visible) {
          setHasBeenVisible(true);
          if (sticky) {
            observer.unobserve(element);
          }
        }
      },
      { rootMargin, threshold }
    );

    observer.observe(element);
    return () => observer.unobserve(element);
  }, [rootMargin, threshold, sticky, hasBeenVisible]);

  return { ref, isVisible: sticky ? hasBeenVisible : isVisible, hasBeenVisible };
}
