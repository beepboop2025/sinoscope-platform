import { memo, type ReactElement, type MouseEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Keyboard, X } from 'lucide-react';
import { ALL_SHORTCUTS } from '../../hooks/useKeyboardShortcuts';
import { overlayVariants, modalVariants } from '../../utils/motion';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const categories = [...new Set(ALL_SHORTCUTS.map(s => s.category))];

const ShortcutsModal = memo(({ isOpen, onClose }: ShortcutsModalProps): ReactElement | null => {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <motion.div
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={(e: MouseEvent) => e.stopPropagation()}
            style={{
              background: 'var(--glass-bg-heavy)', backdropFilter: 'blur(20px)',
              border: '1px solid var(--border-2)',
              borderRadius: 12, padding: 24, width: 440, maxWidth: '90vw',
              boxShadow: 'var(--shadow-lg)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Keyboard size={16} color="var(--cyan)" />
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>Keyboard Shortcuts</span>
              </div>
              <button onClick={onClose} className="btn-ghost" style={{ padding: 4 }}>
                <X size={14} />
              </button>
            </div>

            {categories.map(cat => (
              <div key={cat} style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-4)', marginBottom: 8 }}>
                  {cat}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {ALL_SHORTCUTS.filter(s => s.category === cat).map((s, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{s.desc}</span>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {s.keys.map((k, j) => (
                          <kbd key={j} style={{
                            background: 'var(--surface-2)', border: '1px solid var(--border-1)',
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
              </div>
            ))}

            <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-4)', textAlign: 'center' }}>
              Press Esc to close
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
});
ShortcutsModal.displayName = 'ShortcutsModal';
export default ShortcutsModal;
