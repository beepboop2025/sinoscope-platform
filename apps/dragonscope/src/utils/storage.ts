export const safeJsonParse = <T = unknown>(raw: unknown, fallback: T = null as T): T => {
  if (!raw || typeof raw !== "string") return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
};

export const storageRead = <T = unknown>(key: string, fallback: T = null as T): T => {
  if (typeof window === "undefined") return fallback;
  try {
    return safeJsonParse<T>(window.localStorage.getItem(key), fallback);
  } catch {
    return fallback;
  }
};

export const storageWrite = (key: string, value: unknown): boolean => {
  if (typeof window === "undefined") return false;
  try {
    const serialized = JSON.stringify(value);
    if (serialized.length > 4 * 1024 * 1024) {
      console.warn(`[Storage] Payload for "${key}" is ${(serialized.length / 1024 / 1024).toFixed(1)}MB`);
    }
    window.localStorage.setItem(key, serialized);
    return true;
  } catch (err: unknown) {
    if ((err as DOMException)?.name === "QuotaExceededError") {
      try {
        window.localStorage.removeItem(key);
        window.localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch {
        return false;
      }
    }
    return false;
  }
};
