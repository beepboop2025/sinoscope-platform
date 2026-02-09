let _idCounter = 0;
export const createId = (prefix = 'ds') => `${prefix}_${Date.now().toString(36)}_${(++_idCounter).toString(36)}`;

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export const debounce = (fn, ms) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
};

export const throttle = (fn, ms) => {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last >= ms) {
      last = now;
      fn(...args);
    }
  };
};

/** Fetch with timeout — aborts request if it takes longer than timeoutMs */
export async function fetchWithTimeout(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(timeoutId);
  }
}
