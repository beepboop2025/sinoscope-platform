import { useState, useEffect, useCallback } from 'react';
import { COMMANDS } from '../constants/commands';

type CommandEntry = (typeof COMMANDS)[number];

interface UseCommandBarOptions {
  onCommand?: (cmd: CommandEntry) => void;
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

export function useCommandBar({ onCommand }: UseCommandBarOptions): UseCommandBarReturn {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [query, setQuery] = useState<string>('');
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [showShortcuts, setShowShortcuts] = useState<boolean>(false);

  const filtered = query
    ? COMMANDS.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.desc.toLowerCase().includes(query.toLowerCase()) ||
        c.id.toLowerCase().includes(query.toLowerCase())
      )
    : COMMANDS;

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
