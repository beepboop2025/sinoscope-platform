let _idCounter = 0;
export const createId = (prefix: string = 'ds'): string => `${prefix}_${Date.now().toString(36)}_${(++_idCounter).toString(36)}`;

export const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

export const debounce = <T extends (...args: any[]) => void>(fn: T, ms: number): ((...args: Parameters<T>) => void) => {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
};

export const throttle = <T extends (...args: any[]) => void>(fn: T, ms: number): ((...args: Parameters<T>) => void) => {
  let last = 0;
  return (...args: Parameters<T>) => {
    const now = Date.now();
    if (now - last >= ms) {
      last = now;
      fn(...args);
    }
  };
};

/** Fetch with timeout — aborts request if it takes longer than timeoutMs */
export async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs: number = 10000): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(timeoutId);
  }
}
