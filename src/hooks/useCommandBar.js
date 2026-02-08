import { useState, useEffect, useCallback } from 'react';
import { COMMANDS } from '../constants/commands';

export function useCommandBar({ onCommand }) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const filtered = query
    ? COMMANDS.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.desc.toLowerCase().includes(query.toLowerCase()) ||
        c.id.toLowerCase().includes(query.toLowerCase())
      )
    : COMMANDS;

  useEffect(() => {
    const handler = (e) => {
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
        const tag = e.target?.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) return;
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

  const execute = useCallback((cmd) => {
    setIsOpen(false);
    setQuery('');
    onCommand?.(cmd);
  }, [onCommand]);

  const handleKeyDown = useCallback((e) => {
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
  };
}
