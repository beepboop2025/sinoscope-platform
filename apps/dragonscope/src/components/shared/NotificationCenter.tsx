import { useState, memo, useRef, useEffect, type ReactElement } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bell, X, Check, CheckCheck, Trash2, TrendingUp, Brain, Activity, Zap } from 'lucide-react';
import { useNotifications, type Notification } from '../../stores/notifications';

const TYPE_CONFIG: Record<string, { icon: typeof Bell; color: string; label: string }> = {
  price: { icon: TrendingUp, color: 'var(--green)', label: 'Price Alert' },
  ml: { icon: Brain, color: 'var(--purple)', label: 'ML Signal' },
  system: { icon: Activity, color: 'var(--cyan)', label: 'System' },
  technical: { icon: Zap, color: 'var(--amber)', label: 'Technical' },
};

function timeAgo(ts: number): string {
  const secs = Math.round((Date.now() - ts) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const NotificationItem = memo(({ notification, onMarkRead, onRemove }: {
  notification: Notification;
  onMarkRead: (id: string) => void;
  onRemove: (id: string) => void;
}): ReactElement => {
  const config = TYPE_CONFIG[notification.type] || TYPE_CONFIG.system;
  const Icon = config.icon;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      style={{
        display: 'flex',
        gap: 10,
        padding: '10px 12px',
        background: notification.read ? 'transparent' : 'var(--surface-1)',
        borderRadius: 'var(--radius-md)',
        border: `1px solid ${notification.read ? 'var(--border-1)' : 'var(--border-2)'}`,
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
      onClick={() => !notification.read && onMarkRead(notification.id)}
    >
      <div style={{
        width: 28,
        height: 28,
        borderRadius: 6,
        background: `${config.color}15`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon size={13} color={config.color} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-1)', marginBottom: 2 }}>
          {notification.title}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-3)', lineHeight: 1.3 }}>
          {notification.message}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
          <span style={{ fontSize: 9, color: config.color, fontWeight: 500 }}>{config.label}</span>
          <span style={{ fontSize: 9, color: 'var(--text-4)' }}>{timeAgo(notification.timestamp)}</span>
        </div>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(notification.id); }}
        aria-label="Remove notification"
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-4)',
          cursor: 'pointer',
          padding: 2,
          display: 'flex',
          alignSelf: 'flex-start',
          flexShrink: 0,
        }}
      >
        <X size={12} />
      </button>
    </motion.div>
  );
});
NotificationItem.displayName = 'NotificationItem';

const NotificationCenter = memo((): ReactElement => {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const { notifications, unreadCount, markAsRead, markAllRead, clearAll, removeNotification } = useNotifications();

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  return (
    <div style={{ position: 'relative' }} ref={panelRef}>
      {/* Bell button */}
      <button
        className="btn-ghost"
        onClick={() => setOpen(o => !o)}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        style={{ padding: '4px 8px', position: 'relative' }}
      >
        <Bell size={14} />
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute',
            top: -2,
            right: -2,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: 'var(--red)',
            color: 'white',
            fontSize: 9,
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '2px solid var(--bg-1)',
          }}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 8,
              width: 340,
              maxHeight: 440,
              background: 'var(--glass-bg-heavy)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid var(--border-2)',
              borderRadius: 'var(--radius-xl)',
              boxShadow: 'var(--shadow-lg)',
              overflow: 'hidden',
              zIndex: 'var(--z-dropdown)',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px',
              borderBottom: '1px solid var(--border-1)',
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>
                Notifications
                {unreadCount > 0 && (
                  <span style={{ fontSize: 10, color: 'var(--cyan)', marginLeft: 6 }}>
                    {unreadCount} new
                  </span>
                )}
              </span>
              <div style={{ display: 'flex', gap: 4 }}>
                {unreadCount > 0 && (
                  <button
                    className="btn-ghost"
                    onClick={markAllRead}
                    title="Mark all as read"
                    style={{ padding: '2px 6px', fontSize: 10 }}
                  >
                    <CheckCheck size={12} />
                  </button>
                )}
                {notifications.length > 0 && (
                  <button
                    className="btn-ghost"
                    onClick={clearAll}
                    title="Clear all"
                    style={{ padding: '2px 6px', fontSize: 10 }}
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            </div>

            {/* List */}
            <div style={{ overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
              {notifications.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '32px 16px',
                  color: 'var(--text-4)',
                  fontSize: 12,
                }}>
                  <Bell size={24} style={{ marginBottom: 8, opacity: 0.3 }} />
                  <div>No notifications yet</div>
                  <div style={{ fontSize: 10, marginTop: 4 }}>Market alerts and signals will appear here</div>
                </div>
              ) : (
                <AnimatePresence mode="popLayout">
                  {notifications.map(n => (
                    <NotificationItem
                      key={n.id}
                      notification={n}
                      onMarkRead={markAsRead}
                      onRemove={removeNotification}
                    />
                  ))}
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});
NotificationCenter.displayName = 'NotificationCenter';
export default NotificationCenter;
