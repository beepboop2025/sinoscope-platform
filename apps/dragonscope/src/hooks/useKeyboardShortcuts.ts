import { useEffect, useCallback } from 'react';

interface ShortcutAction {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
  handler: () => void;
  /** If true, only fires when no input/textarea is focused */
  global?: boolean;
}

interface UseKeyboardShortcutsOptions {
  onOpenCommandBar: () => void;
  onToggleShortcuts: () => void;
  onPrevWorkspace: () => void;
  onNextWorkspace: () => void;
  onWorkspace: (index: number) => void;
  onAddPanel?: () => void;
  onFullscreenPanel?: () => void;
}

function isInputFocused(): boolean {
  const tag = document.activeElement?.tagName?.toLowerCase();
  return tag === 'input' || tag === 'textarea' || (document.activeElement as HTMLElement)?.isContentEditable === true;
}

export function useKeyboardShortcuts({
  onOpenCommandBar,
  onToggleShortcuts,
  onPrevWorkspace,
  onNextWorkspace,
  onWorkspace,
  onAddPanel,
  onFullscreenPanel,
}: UseKeyboardShortcutsOptions): void {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const meta = e.metaKey || e.ctrlKey;

    // Cmd+K — open command bar
    if (meta && e.key === 'k') {
      e.preventDefault();
      onOpenCommandBar();
      return;
    }

    // Cmd+? or Cmd+/ — toggle shortcuts
    if (meta && (e.key === '?' || e.key === '/')) {
      e.preventDefault();
      onToggleShortcuts();
      return;
    }

    // Cmd+Shift+N — add panel
    if (meta && e.shiftKey && e.key === 'N') {
      e.preventDefault();
      onAddPanel?.();
      return;
    }

    // Cmd+Shift+F — fullscreen panel
    if (meta && e.shiftKey && e.key === 'F') {
      e.preventDefault();
      onFullscreenPanel?.();
      return;
    }

    // Skip global shortcuts when input is focused
    if (isInputFocused()) return;

    // / — search (same as Cmd+K)
    if (e.key === '/' && !meta) {
      e.preventDefault();
      onOpenCommandBar();
      return;
    }

    // ? — show shortcuts
    if (e.key === '?' && !meta) {
      e.preventDefault();
      onToggleShortcuts();
      return;
    }

    // [ — prev workspace
    if (e.key === '[' && !meta) {
      e.preventDefault();
      onPrevWorkspace();
      return;
    }

    // ] — next workspace
    if (e.key === ']' && !meta) {
      e.preventDefault();
      onNextWorkspace();
      return;
    }

    // 1-9 — switch workspace
    if (!meta && !e.altKey && e.key >= '1' && e.key <= '9') {
      e.preventDefault();
      onWorkspace(parseInt(e.key, 10) - 1);
      return;
    }
  }, [onOpenCommandBar, onToggleShortcuts, onPrevWorkspace, onNextWorkspace, onWorkspace, onAddPanel, onFullscreenPanel]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

// All shortcuts for display in ShortcutsModal
export const ALL_SHORTCUTS = [
  { keys: ['Ctrl', 'K'], desc: 'Open command bar', category: 'Navigation' },
  { keys: ['/'], desc: 'Quick search', category: 'Navigation' },
  { keys: ['1-9'], desc: 'Switch workspace', category: 'Navigation' },
  { keys: ['['], desc: 'Previous workspace', category: 'Navigation' },
  { keys: [']'], desc: 'Next workspace', category: 'Navigation' },
  { keys: ['Ctrl', 'Shift', 'N'], desc: 'Add panel', category: 'Panels' },
  { keys: ['Ctrl', 'Shift', 'F'], desc: 'Fullscreen panel', category: 'Panels' },
  { keys: ['L'], desc: 'Link panel to symbol', category: 'Panels' },
  { keys: ['X'], desc: 'Close panel', category: 'Panels' },
  { keys: ['Ctrl', '?'], desc: 'Show shortcuts', category: 'Help' },
  { keys: ['?'], desc: 'Show shortcuts', category: 'Help' },
  { keys: ['Esc'], desc: 'Close modal / command bar', category: 'Help' },
  { keys: ['Ctrl', 'Enter'], desc: 'Run SQL query', category: 'Panels' },
] as const;
