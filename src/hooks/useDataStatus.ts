import { useEffect, useRef } from 'react';
import { useToast } from '../components/shared/Toast';
import type { MarketSnapshot } from '../types';

type WSStatus = 'mock' | 'live' | 'connecting' | 'connected' | 'disconnected' | 'error';

interface ErrorInfo {
  error: string;
}

export function useDataStatus(marketData: MarketSnapshot | null, wsStatus: WSStatus | string): void {
  const { addToast } = useToast();
  const notifiedRef = useRef<Record<string, boolean>>({});
  const initialRef = useRef<boolean>(true);

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
    const checks: { key: string; label: string; data: Record<string, unknown> | undefined }[] = [
      { key: 'stocks', label: 'Stock data', data: marketData.stocks },
      { key: 'crypto', label: 'Crypto data', data: marketData.crypto },
      { key: 'forex', label: 'Forex data', data: marketData.forex },
    ];

    for (const { key, label, data } of checks) {
      const hasData = data && Object.keys(data).length > 0;
      if (hasData && notifiedRef.current[`empty_${key}`]) {
        // Data recovered — clear the empty flag
        notifiedRef.current[`empty_${key}`] = false;
        addToast(`${label} recovered`, 'success', 3000);
      }
      if (!hasData && notifiedRef.current[`had_${key}`] && !notifiedRef.current[`empty_${key}`]) {
        // Had data before but now empty — warn user
        notifiedRef.current[`empty_${key}`] = true;
        addToast(`${label} is currently unavailable`, 'warning', 5000);
      }
      // Track whether we've ever had data for this source
      if (hasData) {
        notifiedRef.current[`had_${key}`] = true;
      }
    }

    // Surface engine-level errors if present
    if (marketData.errors) {
      for (const [source, errInfo] of Object.entries(marketData.errors)) {
        const errKey = `err_${source}`;
        if (!notifiedRef.current[errKey]) {
          notifiedRef.current[errKey] = true;
          addToast(`${source} feed error: ${(errInfo as unknown as ErrorInfo).error}`, 'error', 5000);
        }
      }
      // Clear error notifications when errors resolve
      for (const key of Object.keys(notifiedRef.current)) {
        if (key.startsWith('err_')) {
          const source = key.slice(4);
          if (!marketData.errors[source]) {
            notifiedRef.current[key] = false;
          }
        }
      }
    }
  }, [marketData, wsStatus, addToast]);
}
