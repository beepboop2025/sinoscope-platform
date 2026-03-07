import { useRef, useEffect, useMemo } from 'react';
import { Command } from 'cmdk';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, ArrowRight, Layout, Plus, TrendingUp } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface CommandItem {
  id: string;
  label: string;
  desc: string;
  shortcut?: string;
  action: string;
  target?: string;
}

interface CommandBarProps {
  isOpen: boolean;
  query: string;
  setQuery: (query: string) => void;
  filtered: CommandItem[];
  activeIndex: number;
  setActiveIndex: (index: number) => void;
  execute: (cmd: CommandItem) => void;
  handleKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onClose: () => void;
}

const ICONS: Record<string, LucideIcon> = {
  workspace: Layout,
  addPanel: Plus,
};

const MAX_VISIBLE = 8;

function getIcon(action: string, id: string): LucideIcon {
  if (id.startsWith('data_')) return TrendingUp;
  return ICONS[action] || ArrowRight;
}

export default function CommandBar({
  isOpen,
  query,
  setQuery,
  filtered,
  activeIndex,
  setActiveIndex,
  execute,
  handleKeyDown,
  onClose,
}: CommandBarProps): React.JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      const raf = requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
      return () => cancelAnimationFrame(raf);
    }
  }, [isOpen]);

  // Auto-scroll the active item into view during keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const container = listRef.current;
    if (!container) return;
    const selected = container.querySelector('[data-selected="true"]');
    if (selected) {
      selected.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [activeIndex, isOpen]);

  // Group items by action type
  const groups = useMemo(() => {
    const workspaces: CommandItem[] = [];
    const addPanels: CommandItem[] = [];
    const actions: CommandItem[] = [];
    const marketData: CommandItem[] = [];

    for (const item of filtered) {
      if (item.id.startsWith('data_')) {
        marketData.push(item);
      } else if (item.action === 'workspace') {
        workspaces.push(item);
      } else if (item.action === 'addPanel') {
        addPanels.push(item);
      } else {
        actions.push(item);
      }
    }

    return { workspaces, addPanels, actions, marketData };
  }, [filtered]);

  const renderGroup = (heading: string, items: CommandItem[], max: number = MAX_VISIBLE) => {
    if (items.length === 0) return null;
    return (
      <Command.Group heading={heading}>
        {items.slice(0, max).map((cmd) => {
          const Icon = getIcon(cmd.action, cmd.id);
          const globalIndex = filtered.indexOf(cmd);
          const isDataItem = cmd.id.startsWith('data_');
          return (
            <Command.Item
              key={cmd.id}
              value={cmd.id}
              onSelect={() => execute(cmd)}
              onMouseEnter={() => setActiveIndex(globalIndex)}
              data-selected={globalIndex === activeIndex ? 'true' : undefined}
            >
              <Icon size={14} className="command-item-icon" aria-hidden="true" color={isDataItem ? 'var(--cyan)' : undefined} />
              <span className="command-item-label">{cmd.label}</span>
              <span className="command-item-desc">{cmd.desc}</span>
              {cmd.shortcut && (
                <span className="command-item-shortcut">{cmd.shortcut}</span>
              )}
            </Command.Item>
          );
        })}
      </Command.Group>
    );
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="command-overlay"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label="Command bar"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <motion.div
            className="command-dialog"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1.0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          >
            <Command
              shouldFilter={false}
              onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === 'Escape') {
                  e.preventDefault();
                  onClose();
                }
              }}
            >
              <div className="cmdk-input-wrapper">
                <Search size={18} color="var(--text-3)" aria-hidden="true" />
                <Command.Input
                  ref={inputRef}
                  value={query}
                  onValueChange={(value: string) => {
                    setQuery(value);
                    setActiveIndex(0);
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a command or search symbols..."
                  aria-label="Search commands and market data"
                />
              </div>

              <Command.List ref={listRef}>
                <Command.Empty>No matching commands or symbols</Command.Empty>

                {/* Market data results appear first when searching */}
                {renderGroup('Market Data', groups.marketData, 6)}
                {renderGroup('Workspaces', groups.workspaces)}
                {renderGroup('Add Panel', groups.addPanels)}
                {renderGroup('Actions', groups.actions)}
              </Command.List>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
