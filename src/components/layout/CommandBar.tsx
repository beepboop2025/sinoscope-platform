import { useRef, useEffect, useMemo } from 'react';
import { Command } from 'cmdk';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, ArrowRight, Layout, Plus } from 'lucide-react';
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

function getIcon(action: string): LucideIcon {
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

  useEffect(() => {
    if (isOpen) {
      // Small delay to ensure the DOM is ready after animation starts
      const raf = requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
      return () => cancelAnimationFrame(raf);
    }
  }, [isOpen]);

  // Group items by action type
  const groups = useMemo(() => {
    const workspaces: CommandItem[] = [];
    const addPanels: CommandItem[] = [];
    const actions: CommandItem[] = [];

    for (const item of filtered) {
      if (item.action === 'workspace') {
        workspaces.push(item);
      } else if (item.action === 'addPanel') {
        addPanels.push(item);
      } else {
        actions.push(item);
      }
    }

    return { workspaces, addPanels, actions };
  }, [filtered]);

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
                  placeholder="Type a command or search..."
                  aria-label="Search commands"
                />
              </div>

              <Command.List>
                <Command.Empty>No matching commands</Command.Empty>

                {groups.workspaces.length > 0 && (
                  <Command.Group heading="Workspaces">
                    {groups.workspaces.slice(0, MAX_VISIBLE).map((cmd, i) => {
                      const Icon = getIcon(cmd.action);
                      const globalIndex = filtered.indexOf(cmd);
                      return (
                        <Command.Item
                          key={cmd.id}
                          value={cmd.id}
                          onSelect={() => execute(cmd)}
                          onMouseEnter={() => setActiveIndex(globalIndex)}
                          data-selected={globalIndex === activeIndex ? 'true' : undefined}
                        >
                          <Icon size={14} className="command-item-icon" aria-hidden="true" />
                          <span className="command-item-label">{cmd.label}</span>
                          <span className="command-item-desc">{cmd.desc}</span>
                          {cmd.shortcut && (
                            <span className="command-item-shortcut">{cmd.shortcut}</span>
                          )}
                        </Command.Item>
                      );
                    })}
                  </Command.Group>
                )}

                {groups.addPanels.length > 0 && (
                  <Command.Group heading="Add Panel">
                    {groups.addPanels.slice(0, MAX_VISIBLE).map((cmd) => {
                      const Icon = getIcon(cmd.action);
                      const globalIndex = filtered.indexOf(cmd);
                      return (
                        <Command.Item
                          key={cmd.id}
                          value={cmd.id}
                          onSelect={() => execute(cmd)}
                          onMouseEnter={() => setActiveIndex(globalIndex)}
                          data-selected={globalIndex === activeIndex ? 'true' : undefined}
                        >
                          <Icon size={14} className="command-item-icon" aria-hidden="true" />
                          <span className="command-item-label">{cmd.label}</span>
                          <span className="command-item-desc">{cmd.desc}</span>
                          {cmd.shortcut && (
                            <span className="command-item-shortcut">{cmd.shortcut}</span>
                          )}
                        </Command.Item>
                      );
                    })}
                  </Command.Group>
                )}

                {groups.actions.length > 0 && (
                  <Command.Group heading="Actions">
                    {groups.actions.slice(0, MAX_VISIBLE).map((cmd) => {
                      const Icon = getIcon(cmd.action);
                      const globalIndex = filtered.indexOf(cmd);
                      return (
                        <Command.Item
                          key={cmd.id}
                          value={cmd.id}
                          onSelect={() => execute(cmd)}
                          onMouseEnter={() => setActiveIndex(globalIndex)}
                          data-selected={globalIndex === activeIndex ? 'true' : undefined}
                        >
                          <Icon size={14} className="command-item-icon" aria-hidden="true" />
                          <span className="command-item-label">{cmd.label}</span>
                          <span className="command-item-desc">{cmd.desc}</span>
                          {cmd.shortcut && (
                            <span className="command-item-shortcut">{cmd.shortcut}</span>
                          )}
                        </Command.Item>
                      );
                    })}
                  </Command.Group>
                )}
              </Command.List>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
