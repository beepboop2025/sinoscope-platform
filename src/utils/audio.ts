// Programmatic sound generation via Web Audio API — no external audio files needed.

export type SoundName =
  | 'alertChime'
  | 'achievement'
  | 'success'
  | 'fail'
  | 'pop'
  | 'disconnect'
  | 'reconnect';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let ctx: AudioContext | null = null;
let soundEnabled = true;
let masterVolume = 0.3;

/** Lazily create (or resume) the AudioContext. Returns null if unavailable. */
function getContext(): AudioContext | null {
  try {
    if (!ctx) {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    // Browsers suspend contexts created before a user gesture — resume if needed.
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
    return ctx;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface OscConfig {
  type: OscillatorType;
  frequency: number;
  endFrequency?: number;
  startTime: number;
  stopTime: number;
  gainEnvelope: GainPoint[];
}

interface GainPoint {
  value: number;
  time: number;
}

/** Create an oscillator + gain pair and schedule it. */
function scheduleOsc(audio: AudioContext, dest: AudioNode, cfg: OscConfig): void {
  const osc = audio.createOscillator();
  const gain = audio.createGain();

  osc.type = cfg.type;
  osc.frequency.setValueAtTime(cfg.frequency, cfg.startTime);
  if (cfg.endFrequency !== undefined) {
    osc.frequency.linearRampToValueAtTime(cfg.endFrequency, cfg.stopTime);
  }

  // Build gain envelope
  gain.gain.setValueAtTime(0, cfg.startTime);
  for (const pt of cfg.gainEnvelope) {
    gain.gain.linearRampToValueAtTime(pt.value * masterVolume, pt.time);
  }

  osc.connect(gain);
  gain.connect(dest);
  osc.start(cfg.startTime);
  osc.stop(cfg.stopTime);
}

// ---------------------------------------------------------------------------
// Sound implementations
// ---------------------------------------------------------------------------

/** Soft ascending 2-tone chime (440 Hz -> 660 Hz, sine, 0.5 s) */
export function alertChime(): void {
  const audio = getContext();
  if (!audio || !soundEnabled) return;
  const now = audio.currentTime;

  // First tone: 440 Hz
  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 440,
    startTime: now,
    stopTime: now + 0.25,
    gainEnvelope: [
      { value: 0.6, time: now + 0.02 },
      { value: 0.0, time: now + 0.25 },
    ],
  });

  // Second tone: 660 Hz
  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 660,
    startTime: now + 0.2,
    stopTime: now + 0.5,
    gainEnvelope: [
      { value: 0.6, time: now + 0.22 },
      { value: 0.0, time: now + 0.5 },
    ],
  });
}

/** Celebratory C-E-G major chord arpeggio (1.5 s) */
export function achievement(): void {
  const audio = getContext();
  if (!audio || !soundEnabled) return;
  const now = audio.currentTime;

  const notes = [261.63, 329.63, 392.0]; // C4, E4, G4
  const stagger = 0.12;

  notes.forEach((freq, i) => {
    const start = now + i * stagger;
    scheduleOsc(audio, audio.destination, {
      type: 'sine',
      frequency: freq,
      startTime: start,
      stopTime: start + 1.2,
      gainEnvelope: [
        { value: 0.5, time: start + 0.03 },
        { value: 0.35, time: start + 0.3 },
        { value: 0.0, time: start + 1.2 },
      ],
    });
  });

  // High octave shimmer on top
  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 523.25, // C5
    startTime: now + 0.4,
    stopTime: now + 1.5,
    gainEnvelope: [
      { value: 0.3, time: now + 0.43 },
      { value: 0.15, time: now + 0.8 },
      { value: 0.0, time: now + 1.5 },
    ],
  });
}

/** Cash register ding (1200 Hz sine, quick decay, 0.8 s) */
export function success(): void {
  const audio = getContext();
  if (!audio || !soundEnabled) return;
  const now = audio.currentTime;

  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 1200,
    startTime: now,
    stopTime: now + 0.8,
    gainEnvelope: [
      { value: 0.7, time: now + 0.01 },
      { value: 0.1, time: now + 0.08 },
      { value: 0.05, time: now + 0.3 },
      { value: 0.0, time: now + 0.8 },
    ],
  });

  // Subtle harmonic at 2400 Hz for brightness
  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 2400,
    startTime: now,
    stopTime: now + 0.3,
    gainEnvelope: [
      { value: 0.2, time: now + 0.01 },
      { value: 0.0, time: now + 0.3 },
    ],
  });
}

/** Gentle descending tone (440 Hz -> 220 Hz, 0.5 s) */
export function fail(): void {
  const audio = getContext();
  if (!audio || !soundEnabled) return;
  const now = audio.currentTime;

  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 440,
    endFrequency: 220,
    startTime: now,
    stopTime: now + 0.5,
    gainEnvelope: [
      { value: 0.5, time: now + 0.02 },
      { value: 0.3, time: now + 0.15 },
      { value: 0.0, time: now + 0.5 },
    ],
  });
}

/** Subtle UI click (800 Hz, very fast decay, 0.1 s) */
export function pop(): void {
  const audio = getContext();
  if (!audio || !soundEnabled) return;
  const now = audio.currentTime;

  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 800,
    startTime: now,
    stopTime: now + 0.1,
    gainEnvelope: [
      { value: 0.4, time: now + 0.005 },
      { value: 0.0, time: now + 0.1 },
    ],
  });
}

/** Low warning tone (200 Hz, 0.3 s) */
export function disconnect(): void {
  const audio = getContext();
  if (!audio || !soundEnabled) return;
  const now = audio.currentTime;

  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 200,
    startTime: now,
    stopTime: now + 0.3,
    gainEnvelope: [
      { value: 0.5, time: now + 0.02 },
      { value: 0.3, time: now + 0.1 },
      { value: 0.0, time: now + 0.3 },
    ],
  });
}

/** Ascending reconnect tone (300 Hz -> 500 Hz, 0.3 s) */
export function reconnect(): void {
  const audio = getContext();
  if (!audio || !soundEnabled) return;
  const now = audio.currentTime;

  scheduleOsc(audio, audio.destination, {
    type: 'sine',
    frequency: 300,
    endFrequency: 500,
    startTime: now,
    stopTime: now + 0.3,
    gainEnvelope: [
      { value: 0.5, time: now + 0.02 },
      { value: 0.3, time: now + 0.15 },
      { value: 0.0, time: now + 0.3 },
    ],
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

const soundMap: Record<SoundName, () => void> = {
  alertChime,
  achievement,
  success,
  fail,
  pop,
  disconnect,
  reconnect,
};

/** Play a sound by name. Silently no-ops if audio is unavailable or disabled. */
export function playSound(name: SoundName): void {
  try {
    soundMap[name]();
  } catch {
    // Silently swallow — audio should never crash the app.
  }
}

/** Enable or disable all sound playback. */
export function setSoundEnabled(enabled: boolean): void {
  soundEnabled = enabled;
}

/** Set master volume (clamped to 0 .. 1). Default is 0.3. */
export function setSoundVolume(volume: number): void {
  masterVolume = Math.max(0, Math.min(1, volume));
}

/** Check whether sound is currently enabled. */
export function isSoundEnabled(): boolean {
  return soundEnabled;
}

/** Get the current master volume. */
export function getSoundVolume(): number {
  return masterVolume;
}
