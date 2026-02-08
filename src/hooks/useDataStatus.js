import { useEffect, useRef } from 'react';
import { useToast } from '../components/shared/Toast';

/**
 * Monitors market data sources and notifies user via toast
 * when data appears to be mock/stale.
 */
export function useDataStatus(marketData, wsStatus) {
  const { addToast } = useToast();
  const notifiedRef = useRef({});
  const initialRef = useRef(true);

  useEffect(() => {
    // Skip the initial render
    if (initialRef.current) {
      initialRef.current = false;
      return;
    }

    if (!marketData) return;

    // Check if we fell back to mock mode
    if (wsStatus === 'mock' && !notifiedRef.current.mock) {
      notifiedRef.current.mock = true;
      addToast('Live data unavailable — using simulated market data', 'warning', 6000);
    }

    // Notify when live data connects
    if (wsStatus === 'live' && notifiedRef.current.mock) {
      notifiedRef.current.mock = false;
      addToast('Connected to live market data', 'success', 3000);
    }

    // Check if specific data sources are empty
    const checks = [
      { key: 'stocks', label: 'Stock data', data: marketData.stocks },
      { key: 'crypto', label: 'Crypto data', data: marketData.crypto },
      { key: 'forex', label: 'Forex data', data: marketData.forex },
    ];

    for (const { key, label, data } of checks) {
      const hasData = data && Object.keys(data).length > 0;
      if (hasData && notifiedRef.current[`empty_${key}`]) {
        notifiedRef.current[`empty_${key}`] = false;
      }
    }
  }, [marketData, wsStatus, addToast]);
}
