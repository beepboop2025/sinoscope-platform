import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { setSoundEnabled, setSoundVolume } from '../utils/audio';

export interface SettingsState {
  // Appearance
  theme: 'dark' | 'light';
  glassIntensity: number; // 0-100, maps to blur amount
  animationsEnabled: boolean;

  // Gamification
  gamificationEnabled: boolean;
  showXPBar: boolean;
  showStreak: boolean;
  soundOnAchievement: boolean;

  // Audio
  soundEnabled: boolean;
  soundVolume: number; // 0-1

  // Data
  refreshInterval: number; // seconds
  useMockFallback: boolean;
  maxCacheAge: number; // seconds

  // Actions
  setSetting: <K extends keyof SettingsState>(key: K, value: SettingsState[K]) => void;
}

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      // Defaults
      theme: 'dark',
      glassIntensity: 70,
      animationsEnabled: true,

      gamificationEnabled: true,
      showXPBar: true,
      showStreak: true,
      soundOnAchievement: true,

      soundEnabled: false,
      soundVolume: 0.3,

      refreshInterval: 5,
      useMockFallback: true,
      maxCacheAge: 300,

      setSetting: (key, value) => {
        set({ [key]: value } as Partial<SettingsState>);

        // Side effects for audio settings
        if (key === 'soundEnabled') setSoundEnabled(value as boolean);
        if (key === 'soundVolume') setSoundVolume(value as number);
      },
    }),
    {
      name: 'dragonscope-settings',
      partialize: (state) => {
        const { setSetting: _, ...rest } = state;
        return rest;
      },
      storage: {
        getItem: (name) => {
          try {
            const str = localStorage.getItem(name);
            return str ? JSON.parse(str) : null;
          } catch { return null; }
        },
        setItem: (name, value) => {
          try {
            localStorage.setItem(name, JSON.stringify(value));
          } catch (e) {
            if (e instanceof DOMException && e.name === 'QuotaExceededError') {
              console.warn('[Settings] localStorage quota exceeded');
            }
          }
        },
        removeItem: (name) => {
          try { localStorage.removeItem(name); } catch {}
        },
      },
    }
  )
);
