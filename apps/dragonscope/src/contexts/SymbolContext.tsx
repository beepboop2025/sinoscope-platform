import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  type ReactElement,
  type ReactNode,
} from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SymbolType = 'stock' | 'crypto' | 'forex';

export interface SymbolState {
  /** Currently active ticker symbol, e.g. "AAPL" or "BTC" */
  activeSymbol: string;
  /** Asset class of the active symbol */
  symbolType: SymbolType;
  /** Panel IDs that are linked — they all react to symbol changes */
  linkedPanels: Set<string>;
  /** Rolling history of the last 20 symbols the user navigated to */
  symbolHistory: string[];
}

export interface SymbolContextValue extends SymbolState {
  /**
   * Set the active symbol across all linked panels.
   * Appends to symbolHistory (capped at 20, deduped against head).
   */
  setActiveSymbol: (symbol: string, type: SymbolType) => void;
  /** Toggle whether a panel participates in linked-symbol updates. */
  togglePanelLink: (panelId: string) => void;
  /** Check if a specific panel is currently linked. */
  isPanelLinked: (panelId: string) => boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_HISTORY = 20;
const STORAGE_KEY = 'dragonscope-symbol-state';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface PersistedSymbolState {
  activeSymbol: string;
  symbolType: SymbolType;
  linkedPanels: string[];
  symbolHistory: string[];
}

function loadPersistedState(): Partial<PersistedSymbolState> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Partial<PersistedSymbolState>;
  } catch {
    return null;
  }
}

function persistState(state: SymbolState): void {
  try {
    const serialisable: PersistedSymbolState = {
      activeSymbol: state.activeSymbol,
      symbolType: state.symbolType,
      linkedPanels: Array.from(state.linkedPanels),
      symbolHistory: state.symbolHistory,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serialisable));
  } catch {
    // QuotaExceededError or localStorage unavailable — silently ignore
  }
}

function buildInitialState(): SymbolState {
  const saved = loadPersistedState();
  return {
    activeSymbol: saved?.activeSymbol ?? 'BTC',
    symbolType: (saved?.symbolType as SymbolType) ?? 'crypto',
    linkedPanels: new Set<string>(saved?.linkedPanels ?? []),
    symbolHistory: saved?.symbolHistory ?? ['BTC'],
  };
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const SymbolContext = createContext<SymbolContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface SymbolProviderProps {
  children: ReactNode;
}

export function SymbolProvider({ children }: SymbolProviderProps): ReactElement {
  const [state, setState] = useState<SymbolState>(buildInitialState);

  // ---- setActiveSymbol ----------------------------------------------------

  const setActiveSymbol = useCallback((symbol: string, type: SymbolType): void => {
    if (!symbol) return;
    const normalised = symbol.toUpperCase().trim();
    if (!normalised) return;

    setState((prev) => {
      // Skip no-op updates
      if (prev.activeSymbol === normalised && prev.symbolType === type) {
        return prev;
      }

      // Build new history: avoid duplicate at head, cap at MAX_HISTORY
      const history =
        prev.symbolHistory[0] === normalised
          ? prev.symbolHistory
          : [normalised, ...prev.symbolHistory].slice(0, MAX_HISTORY);

      const next: SymbolState = {
        ...prev,
        activeSymbol: normalised,
        symbolType: type,
        symbolHistory: history,
      };
      persistState(next);
      return next;
    });
  }, []);

  // ---- togglePanelLink ----------------------------------------------------

  const togglePanelLink = useCallback((panelId: string): void => {
    if (!panelId) return;

    setState((prev) => {
      const nextLinked = new Set(prev.linkedPanels);
      if (nextLinked.has(panelId)) {
        nextLinked.delete(panelId);
      } else {
        nextLinked.add(panelId);
      }

      const next: SymbolState = { ...prev, linkedPanels: nextLinked };
      persistState(next);
      return next;
    });
  }, []);

  // ---- isPanelLinked (stable ref) -----------------------------------------

  const isPanelLinked = useCallback(
    (panelId: string): boolean => state.linkedPanels.has(panelId),
    [state.linkedPanels],
  );

  // ---- Memoised context value ---------------------------------------------

  const value = useMemo<SymbolContextValue>(
    () => ({
      activeSymbol: state.activeSymbol,
      symbolType: state.symbolType,
      linkedPanels: state.linkedPanels,
      symbolHistory: state.symbolHistory,
      setActiveSymbol,
      togglePanelLink,
      isPanelLinked,
    }),
    [state, setActiveSymbol, togglePanelLink, isPanelLinked],
  );

  return (
    <SymbolContext.Provider value={value}>
      {children}
    </SymbolContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Consumer hook
// ---------------------------------------------------------------------------

/**
 * Access the shared symbol state and actions.
 * Must be rendered inside a `<SymbolProvider>`.
 */
export function useSymbol(): SymbolContextValue {
  const ctx = useContext(SymbolContext);
  if (!ctx) {
    throw new Error('useSymbol must be used within a <SymbolProvider>');
  }
  return ctx;
}
