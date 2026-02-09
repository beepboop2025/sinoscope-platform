import { useState, useEffect } from 'react';
import { WifiOff, Wifi } from 'lucide-react';

export default function OfflineIndicator() {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [showReconnected, setShowReconnected] = useState(false);

  useEffect(() => {
    const goOffline = () => setIsOffline(true);
    const goOnline = () => {
      setIsOffline(false);
      setShowReconnected(true);
      setTimeout(() => setShowReconnected(false), 3000);
    };

    window.addEventListener('offline', goOffline);
    window.addEventListener('online', goOnline);
    return () => {
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('online', goOnline);
    };
  }, []);

  if (!isOffline && !showReconnected) return null;

  const style = {
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 10000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: '8px 16px',
    fontSize: 12,
    fontWeight: 600,
    fontFamily: "'JetBrains Mono', monospace",
    color: '#fff',
    background: isOffline ? 'rgba(220, 38, 38, 0.9)' : 'rgba(22, 163, 74, 0.9)',
    backdropFilter: 'blur(8px)',
    transition: 'background 0.3s, opacity 0.3s',
  };

  return (
    <div style={style} role="status" aria-live="polite">
      {isOffline ? (
        <>
          <WifiOff size={14} />
          <span>Offline — showing cached data</span>
        </>
      ) : (
        <>
          <Wifi size={14} />
          <span>Back online — syncing...</span>
        </>
      )}
    </div>
  );
}
