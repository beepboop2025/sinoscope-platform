import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ACHIEVEMENTS, type Achievement } from '../constants/achievements';
import { XP_ACTIONS, getLevelForXP } from '../constants/xpActions';

interface XPEvent {
  action: string;
  xp: number;
  timestamp: number;
}

interface Prediction {
  id: string;
  symbol: string;
  direction: 'up' | 'down';
  targetPrice: number;
  createdAt: number;
  expiresAt: number;
  resolved: boolean;
  correct?: boolean;
}

interface GamificationState {
  xp: number;
  level: number;
  streak: number;
  lastActiveDate: string | null;
  achievements: string[];
  predictions: Prediction[];
  xpHistory: XPEvent[];
  commandBarUses: number;
  sqlQueryCount: number;
  panelsAdded: number;
  workspacesVisited: Set<string>;

  // Actions
  addXP: (action: string, reason?: string) => void;
  checkStreak: () => void;
  unlockAchievement: (id: string) => void;
  addPrediction: (prediction: Omit<Prediction, 'id' | 'resolved'>) => void;
  resolvePrediction: (id: string, correct: boolean) => void;
  trackWorkspace: (id: string) => void;
  trackCommandBar: () => void;
  trackSqlQuery: () => void;
  trackPanelAdd: () => void;
}

function todayStr(): string {
  return new Date().toISOString().split('T')[0];
}

export const useGamification = create<GamificationState>()(
  persist(
    (set, get) => ({
      xp: 0,
      level: 1,
      streak: 0,
      lastActiveDate: null,
      achievements: [],
      predictions: [],
      xpHistory: [],
      commandBarUses: 0,
      sqlQueryCount: 0,
      panelsAdded: 0,
      workspacesVisited: new Set<string>(),

      addXP: (action: string) => {
        const config = XP_ACTIONS[action];
        if (!config) return;

        set((state) => {
          const newXP = state.xp + config.xp;
          const newLevel = getLevelForXP(newXP);
          const event: XPEvent = { action, xp: config.xp, timestamp: Date.now() };

          return {
            xp: newXP,
            level: newLevel,
            xpHistory: [...state.xpHistory.slice(-99), event],
          };
        });
      },

      checkStreak: () => {
        const today = todayStr();
        const state = get();

        if (state.lastActiveDate === today) return; // Already checked today

        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const yesterdayStr = yesterday.toISOString().split('T')[0];

        let newStreak = 1;
        if (state.lastActiveDate === yesterdayStr) {
          newStreak = state.streak + 1;
        }

        set({ streak: newStreak, lastActiveDate: today });

        // Award daily login XP
        get().addXP('daily_login');

        // Streak bonus
        if (newStreak > 1) {
          get().addXP('streak_bonus');
        }

        // Check streak achievements
        if (newStreak >= 3) get().unlockAchievement('streak_3');
        if (newStreak >= 7) get().unlockAchievement('streak_7');
        if (newStreak >= 30) get().unlockAchievement('streak_30');
      },

      unlockAchievement: (id: string) => {
        const state = get();
        if (state.achievements.includes(id)) return;

        const achievement = ACHIEVEMENTS.find((a: Achievement) => a.id === id);
        if (!achievement) return;

        set((s) => ({
          achievements: [...s.achievements, id],
          xp: s.xp + achievement.xpReward,
          level: getLevelForXP(s.xp + achievement.xpReward),
        }));
      },

      addPrediction: (prediction) => {
        const id = `pred_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        set((state) => ({
          predictions: [...state.predictions.slice(-49), { ...prediction, id, resolved: false }],
        }));

        // First prediction achievement
        if (get().predictions.length === 1) {
          get().unlockAchievement('prediction_maker');
        }

        get().addXP('prediction_create');
      },

      resolvePrediction: (id: string, correct: boolean) => {
        set((state) => ({
          predictions: state.predictions.map(p =>
            p.id === id ? { ...p, resolved: true, correct } : p
          ),
        }));

        if (correct) {
          get().addXP('prediction_correct');
          const correctCount = get().predictions.filter(p => p.correct).length;
          if (correctCount >= 5) get().unlockAchievement('prediction_correct');
        }
      },

      trackWorkspace: (id: string) => {
        set((state) => {
          const visited = new Set(state.workspacesVisited);
          visited.add(id);
          return { workspacesVisited: visited };
        });

        get().addXP('workspace_switch');

        if (get().workspacesVisited.size >= 9) {
          get().unlockAchievement('workspace_explorer');
        }
      },

      trackCommandBar: () => {
        set((state) => ({ commandBarUses: state.commandBarUses + 1 }));
        get().addXP('command_bar_use');
        if (get().commandBarUses >= 10) {
          get().unlockAchievement('command_master');
        }
      },

      trackSqlQuery: () => {
        set((state) => ({ sqlQueryCount: state.sqlQueryCount + 1 }));
        get().addXP('sql_query');
        if (get().sqlQueryCount === 1) get().unlockAchievement('data_hunter');
        if (get().sqlQueryCount >= 50) get().unlockAchievement('sql_expert');
      },

      trackPanelAdd: () => {
        set((state) => ({ panelsAdded: state.panelsAdded + 1 }));
        get().addXP('panel_add');
        if (get().panelsAdded >= 5) get().unlockAchievement('panel_customizer');
      },
    }),
    {
      name: 'dragonscope-gamification',
      partialize: (state) => ({
        xp: state.xp,
        level: state.level,
        streak: state.streak,
        lastActiveDate: state.lastActiveDate,
        achievements: state.achievements,
        predictions: state.predictions,
        xpHistory: state.xpHistory,
        commandBarUses: state.commandBarUses,
        sqlQueryCount: state.sqlQueryCount,
        panelsAdded: state.panelsAdded,
        workspacesVisited: [...state.workspacesVisited],
      }),
      merge: (persisted, current) => {
        const p = persisted as Record<string, unknown>;
        return {
          ...current,
          ...p,
          workspacesVisited: new Set(
            Array.isArray(p?.workspacesVisited) ? p.workspacesVisited as string[] : []
          ),
        };
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
              console.warn('[Gamification] localStorage quota exceeded');
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
