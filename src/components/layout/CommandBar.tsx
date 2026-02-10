import { useRef, useEffect } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Search, ArrowRight, Layout, Plus } from 'lucide-react';

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

const ICONS: Record<string, LucideIcon> = { workspace: Layout, addPanel: Plus, export: ArrowRight };

export default function CommandBar({ isOpen, query, setQuery, filtered, activeIndex, setActiveIndex, execute, handleKeyDown, onClose }: CommandBarProps): React.JSX.Element | null {
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = 'command-bar-results';

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="command-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Command bar">
      <div className="command-dialog" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <div className="command-input-wrapper">
          <Search size={18} color="var(--text-3)" aria-hidden="true" />
          <input
            ref={inputRef}
            className="command-input"
            value={query}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setQuery(e.target.value); setActiveIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={filtered[activeIndex] ? `command-option-${filtered[activeIndex].id}` : undefined}
            aria-autocomplete="list"
            aria-label="Search commands"
          />
        </div>
        <div className="command-results" role="listbox" id={listId}>
          {filtered.map((cmd, i) => {
            const Icon = ICONS[cmd.action] || ArrowRight;
            return (
              <div
                key={cmd.id}
                id={`command-option-${cmd.id}`}
                className={`command-item ${i === activeIndex ? 'active' : ''}`}
                onClick={() => execute(cmd)}
                onMouseEnter={() => setActiveIndex(i)}
                role="option"
                aria-selected={i === activeIndex}
              >
                <Icon size={14} color="var(--text-3)" aria-hidden="true" />
                <span className="command-item-label">{cmd.label}</span>
                <span className="command-item-desc">{cmd.desc}</span>
                {cmd.shortcut && <span className="command-item-shortcut">{cmd.shortcut}</span>}
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }} role="option" aria-selected="false">
              No matching commands
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
