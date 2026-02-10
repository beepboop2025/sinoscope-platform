import { memo, type ReactElement, type MouseEvent } from 'react';
import { Keyboard, X } from 'lucide-react';

interface Shortcut {
  keys: string[];
  desc: string;
}

const SHORTCUTS: Shortcut[] = [
  { keys: ['Ctrl', 'K'], desc: 'Open command bar' },
  { keys: ['1-9'], desc: 'Switch workspace' },
  { keys: ['Ctrl', 'Enter'], desc: 'Run SQL query' },
  { keys: ['Esc'], desc: 'Close modal / command bar' },
  { keys: ['Ctrl', '?'], desc: 'Show keyboard shortcuts' },
];

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ShortcutsModal = memo(({ isOpen, onClose }: ShortcutsModalProps): ReactElement | null => {
  if (!isOpen) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.6)', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        onClick={(e: MouseEvent) => e.stopPropagation()}
        style={{
          background: 'var(--bg-1)', border: '1px solid var(--border-2)',
          borderRadius: 10, padding: 20, width: 360, maxWidth: '90vw',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Keyboard size={16} color="var(--cyan)" />
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>Keyboard Shortcuts</span>
          </div>
          <button onClick={onClose} className="btn-ghost" style={{ padding: 4 }}>
            <X size={14} />
          </button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {SHORTCUTS.map((s, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{s.desc}</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {s.keys.map((k, j) => (
                  <kbd key={j} style={{
                    background: 'var(--bg-3)', border: '1px solid var(--border-1)',
                    borderRadius: 4, padding: '2px 6px', fontSize: 10,
                    fontFamily: 'var(--font-mono)', color: 'var(--text-1)',
                  }}>
                    {k}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 14, fontSize: 10, color: 'var(--text-4)', textAlign: 'center' }}>
          Press Esc to close
        </div>
      </div>
    </div>
  );
});
ShortcutsModal.displayName = 'ShortcutsModal';
export default ShortcutsModal;
