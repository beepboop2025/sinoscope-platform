import { memo, useRef, useEffect, useCallback, type ReactElement } from 'react';

interface ECGLineProps {
  /** Whether data is flowing (true = bumps, false = flatline) */
  active?: boolean;
  width?: number;
  height?: number;
  color?: string;
}

const POINTS = 120;
const DRAW_INTERVAL = 50; // 20 fps

const ECGLine = memo<ECGLineProps>(({
  active = true,
  width = 200,
  height = 20,
  color = 'var(--cyan)',
}): ReactElement => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const bufferRef = useRef<Float32Array>(new Float32Array(POINTS).fill(0));
  const offsetRef = useRef(0);
  const lastBumpRef = useRef(0);

  // Trigger a bump (call this on WS message)
  const bump = useCallback(() => {
    lastBumpRef.current = Date.now();
  }, []);

  // Expose bump via data attribute for external triggering
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    (el as unknown as Record<string, unknown>).__ecgBump = bump;
  }, [bump]);

  // Auto-bump on a random interval when active to simulate data flow
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      lastBumpRef.current = Date.now();
    }, 800 + Math.random() * 600);
    return () => clearInterval(id);
  }, [active]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    let raf: number;
    let last = 0;

    const draw = (now: number) => {
      raf = requestAnimationFrame(draw);
      if (now - last < DRAW_INTERVAL) return;
      last = now;

      const buf = bufferRef.current;
      const off = offsetRef.current;

      // Generate next sample
      const timeSinceBump = Date.now() - lastBumpRef.current;
      let sample = 0;
      if (active && timeSinceBump < 300) {
        // ECG-style bump: sharp rise then quick decay
        const t = timeSinceBump / 300;
        sample = Math.sin(t * Math.PI) * (1 - t) * 0.8;
      }
      // Add subtle noise
      if (active) {
        sample += (Math.random() - 0.5) * 0.05;
      }

      buf[off % POINTS] = sample;
      offsetRef.current = off + 1;

      // Draw
      const mid = height / 2;
      const amp = (height / 2) * 0.85;
      ctx.clearRect(0, 0, width, height);

      // Resolve CSS color
      const computedColor = getComputedStyle(canvas).getPropertyValue('--ecg-color').trim() || color;

      ctx.strokeStyle = computedColor;
      ctx.lineWidth = 1.2;
      ctx.lineJoin = 'round';
      ctx.beginPath();

      for (let i = 0; i < POINTS; i++) {
        const idx = ((off - POINTS + i) % POINTS + POINTS) % POINTS;
        const x = (i / (POINTS - 1)) * width;
        const y = mid - buf[idx] * amp;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Fade-out gradient on the left
      const grad = ctx.createLinearGradient(0, 0, 30, 0);
      grad.addColorStop(0, 'var(--bg-base, #0A0A0F)');
      grad.addColorStop(1, 'transparent');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 30, height);
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [width, height, color, active]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width,
        height,
        display: 'block',
        opacity: active ? 0.7 : 0.3,
        ['--ecg-color' as string]: color,
      }}
      aria-hidden="true"
    />
  );
});
ECGLine.displayName = 'ECGLine';
export default ECGLine;
