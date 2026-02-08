import { useRef, useEffect, memo } from 'react';
import { Search, ArrowRight, Layout, Plus } from 'lucide-react';

const ICONS = { workspace: Layout, addPanel: Plus, export: ArrowRight };

export default function CommandBar({ isOpen, query, setQuery, filtered, activeIndex, setActiveIndex, execute, handleKeyDown, onClose }) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="command-overlay" onClick={onClose}>
      <div className="command-dialog" onClick={e => e.stopPropagation()}>
        <div className="command-input-wrapper">
          <Search size={18} color="var(--text-3)" />
          <input
            ref={inputRef}
            className="command-input"
            value={query}
            onChange={e => { setQuery(e.target.value); setActiveIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
          />
        </div>
        <div className="command-results">
          {filtered.map((cmd, i) => {
            const Icon = ICONS[cmd.action] || ArrowRight;
            return (
              <div
                key={cmd.id}
                className={`command-item ${i === activeIndex ? 'active' : ''}`}
                onClick={() => execute(cmd)}
                onMouseEnter={() => setActiveIndex(i)}
              >
                <Icon size={14} color="var(--text-3)" />
                <span className="command-item-label">{cmd.label}</span>
                <span className="command-item-desc">{cmd.desc}</span>
                {cmd.shortcut && <span className="command-item-shortcut">{cmd.shortcut}</span>}
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)', fontSize: 12 }}>
              No matching commands
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
