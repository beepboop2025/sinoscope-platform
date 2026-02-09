const normalizeBounds = (min: number, max: number): [number, number] => {
  const lo = Number(min);
  const hi = Number(max);
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 0];
  return lo <= hi ? [lo, hi] : [hi, lo];
};

export const rand = (min: number, max: number): number => {
  const [lo, hi] = normalizeBounds(min, max);
  return +(lo + Math.random() * (hi - lo)).toFixed(4);
};

export const randInt = (min: number, max: number): number => {
  const [lo, hi] = normalizeBounds(min, max);
  if (lo === hi) return Math.floor(lo);
  return Math.floor(lo + Math.random() * (hi - lo));
};

export const randIntInclusive = (min: number, max: number): number => {
  const [loRaw, hiRaw] = normalizeBounds(min, max);
  const lo = Math.ceil(loRaw);
  const hi = Math.floor(hiRaw);
  if (lo >= hi) return lo;
  return Math.floor(lo + Math.random() * (hi - lo + 1));
};

export const clamp = (v: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, v));
