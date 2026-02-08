const normalizeBounds = (min, max) => {
  const lo = Number(min);
  const hi = Number(max);
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 0];
  return lo <= hi ? [lo, hi] : [hi, lo];
};

export const rand = (min, max) => {
  const [lo, hi] = normalizeBounds(min, max);
  return +(lo + Math.random() * (hi - lo)).toFixed(4);
};

export const randInt = (min, max) => {
  const [lo, hi] = normalizeBounds(min, max);
  if (lo === hi) return Math.floor(lo);
  return Math.floor(lo + Math.random() * (hi - lo));
};

export const randIntInclusive = (min, max) => {
  const [loRaw, hiRaw] = normalizeBounds(min, max);
  const lo = Math.ceil(loRaw);
  const hi = Math.floor(hiRaw);
  if (lo >= hi) return lo;
  return Math.floor(lo + Math.random() * (hi - lo + 1));
};

export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
