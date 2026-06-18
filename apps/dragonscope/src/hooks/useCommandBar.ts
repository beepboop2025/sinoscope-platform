import { useState, useEffect, useCallback, useMemo, useDeferredValue } from 'react';
import { COMMANDS } from '../constants/commands';

type CommandEntry = (typeof COMMANDS)[number];

interface MarketDataForSearch {
  forex?: Record<string, { price?: number; changePct?: number }>;
  stocks?: Record<string, { price?: number; changePct?: number }>;
  crypto?: Record<string, { price?: number; changePct?: number; name?: string }>;
}

interface UseCommandBarOptions {
  onCommand?: (cmd: CommandEntry) => void;
  marketData?: MarketDataForSearch | null;
}

interface UseCommandBarReturn {
  isOpen: boolean;
  setIsOpen: React.Dispatch<React.SetStateAction<boolean>>;
  query: string;
  setQuery: React.Dispatch<React.SetStateAction<string>>;
  filtered: readonly CommandEntry[];
  activeIndex: number;
  setActiveIndex: React.Dispatch<React.SetStateAction<number>>;
  execute: (cmd: CommandEntry) => void;
  handleKeyDown: (e: React.KeyboardEvent) => void;
  showShortcuts: boolean;
  setShowShortcuts: React.Dispatch<React.SetStateAction<boolean>>;
}

export function useCommandBar({ onCommand, marketData }: UseCommandBarOptions): UseCommandBarReturn {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [query, setQuery] = useState<string>('');
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [showShortcuts, setShowShortcuts] = useState<boolean>(false);

  // Build dynamic market data search items
  const dataItems = useMemo((): CommandEntry[] => {
    if (!marketData) return [];
    const items: CommandEntry[] = [];

    if (marketData.stocks) {
      for (const [sym, d] of Object.entries(marketData.stocks)) {
        const pct = (Number(d.changePct) || 0);
        const sign = pct >= 0 ? '+' : '';
        items.push({
          id: `data_stock_${sym}`,
          label: sym,
          desc: `Stock — $${(Number(d.price) || 0).toFixed(2)} (${sign}${pct.toFixed(2)}%)`,
          action: 'addPanel',
          target: 'stocks',
        } as CommandEntry);
      }
    }

    if (marketData.crypto) {
      for (const [sym, d] of Object.entries(marketData.crypto)) {
        const pct = (Number(d.changePct) || 0);
        const sign = pct >= 0 ? '+' : '';
        const label = d.name ? `${sym} (${d.name})` : sym;
        items.push({
          id: `data_crypto_${sym}`,
          label,
          desc: `Crypto — $${(Number(d.price) || 0).toLocaleString()} (${sign}${pct.toFixed(2)}%)`,
          action: 'addPanel',
          target: 'crypto',
        } as CommandEntry);
      }
    }

    if (marketData.forex) {
      for (const [pair, d] of Object.entries(marketData.forex)) {
        const pct = (Number(d.changePct) || 0);
        const sign = pct >= 0 ? '+' : '';
        items.push({
          id: `data_forex_${pair}`,
          label: pair,
          desc: `Forex — ${(Number(d.price) || 0).toFixed(4)} (${sign}${pct.toFixed(2)}%)`,
          action: 'addPanel',
          target: 'forex',
        } as CommandEntry);
      }
    }

    return items;
  }, [marketData]);

  const allCommands = useMemo(() => [...COMMANDS, ...dataItems], [dataItems]);

  // Defer the search query so typing stays responsive even with large data sets
  const deferredQuery = useDeferredValue(query);

  const filtered = deferredQuery
    ? allCommands.filter(c =>
        c.label.toLowerCase().includes(deferredQuery.toLowerCase()) ||
        c.desc.toLowerCase().includes(deferredQuery.toLowerCase()) ||
        c.id.toLowerCase().includes(deferredQuery.toLowerCase())
      )
    : COMMANDS; // Only show static commands when no query

  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && (e.key === '?' || e.key === '/')) {
        e.preventDefault();
        setShowShortcuts(prev => !prev);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(prev => !prev);
        setQuery('');
        setActiveIndex(0);
      }
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
      // Number keys 1-9 switch workspaces (only when not typing in an input)
      if (!isOpen && !e.metaKey && !e.ctrlKey && !e.altKey && e.key >= '1' && e.key <= '9') {
        const target = e.target as HTMLElement;
        const tag = target?.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return;
        const cmd = COMMANDS.find(c => c.shortcut === e.key && c.action === 'workspace');
        if (cmd) {
          e.preventDefault();
          onCommand?.(cmd);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onCommand]);

  const execute = useCallback((cmd: CommandEntry): void => {
    setIsOpen(false);
    setQuery('');
    onCommand?.(cmd);
  }, [onCommand]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent): void => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[activeIndex]) {
      execute(filtered[activeIndex]);
    }
  }, [filtered, activeIndex, execute]);

  return {
    isOpen,
    setIsOpen,
    query,
    setQuery,
    filtered,
    activeIndex,
    setActiveIndex,
    execute,
    handleKeyDown,
    showShortcuts,
    setShowShortcuts,
  };
}
