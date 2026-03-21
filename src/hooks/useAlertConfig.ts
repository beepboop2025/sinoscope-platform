import { useState, useEffect, useCallback } from 'react';
import { storageRead, storageWrite } from '../utils/storage';
import { api } from '../services/apiClient';
import type { AlertConfig, TriggeredAlert, MarketSnapshot } from '../types';

const STORAGE_KEY = 'dragonscope_alert_configs';

interface AlertConfigInput {
  symbol?: string;
  condition: AlertConfig['condition'];
  threshold: number | string;
}

interface UseAlertConfigReturn {
  configs: AlertConfig[];
  addConfig: (config: AlertConfigInput) => Promise<void>;
  removeConfig: (id: string) => Promise<void>;
  toggleConfig: (id: string) => Promise<void>;
  evaluateAlerts: (marketData: MarketSnapshot | null) => TriggeredAlert[];
}

export function useAlertConfig(): UseAlertConfigReturn {
  const [configs, setConfigs] = useState<AlertConfig[]>(() => storageRead<AlertConfig[]>(STORAGE_KEY, []));

  // On mount: try loading from API
  useEffect(() => {
    let cancelled = false;
    api.getAlerts().then(data => {
      if (cancelled) return;
      const arr = data as Record<string, unknown>[];
      if (arr && arr.length >= 0) {
        const normalized: AlertConfig[] = arr.map(a => ({
          id: a.id as string,
          symbol: a.symbol as string,
          condition: a.condition as AlertConfig['condition'],
          threshold: a.threshold as number,
          isActive: a.isActive as boolean,
          createdAt: new Date(a.createdAt as string | number).getTime(),
        }));
        setConfigs(normalized);
        storageWrite(STORAGE_KEY, normalized);
      }
    }).catch(() => {
      // API unavailable — keep localStorage data
    });
    return () => { cancelled = true; };
  }, []);

  // Write-through to localStorage
  useEffect(() => {
    storageWrite(STORAGE_KEY, configs);
  }, [configs]);

  const addConfig = useCallback(async (config: AlertConfigInput): Promise<void> => {
    const threshold = Number(config.threshold);
    if (!Number.isFinite(threshold)) return;
    const alertData = {
      symbol: (config.symbol || '').toUpperCase(),
      condition: config.condition,
      threshold,
    };

    try {
      const created = await api.createAlert(alertData) as Record<string, unknown>;
      setConfigs(prev => [...prev, {
        id: created.id as string,
        ...alertData,
        isActive: true,
        createdAt: new Date(created.createdAt as string | number).getTime(),
      }]);
    } catch {
      // Local-only fallback
      setConfigs(prev => [...prev, {
        id: 'ac_' + Date.now().toString(36),
        ...alertData,
        isActive: true,
        createdAt: Date.now(),
      }]);
    }
  }, []);

  const removeConfig = useCallback(async (id: string): Promise<void> => {
    try {
      await api.deleteAlert(id);
    } catch (err) {
      console.warn('[useAlertConfig] deleteAlert API failed, using local fallback:', err);
    }
    setConfigs(prev => prev.filter(c => c.id !== id));
  }, []);

  const toggleConfig = useCallback(async (id: string): Promise<void> => {
    const config = configs.find(c => c.id === id);
    if (!config) return;
    const newActive = !config.isActive;
    try {
      await api.updateAlert(id, { isActive: newActive });
    } catch (err) {
      console.warn('[useAlertConfig] toggleAlert API failed, using local fallback:', err);
    }
    setConfigs(prev => prev.map(c => c.id === id ? { ...c, isActive: newActive } : c));
  }, [configs]);

  const evaluateAlerts = useCallback((marketData: MarketSnapshot | null): TriggeredAlert[] => {
    if (!marketData) return [];
    const triggered: TriggeredAlert[] = [];

    for (const config of configs) {
      if (!config.isActive) continue;
      const price = getSymbolPrice(config.symbol, marketData);
      const changePct = getSymbolChangePct(config.symbol, marketData);
      if (price === null) continue;

      let isTriggered = false;
      let message = '';

      const safePrice = Number(price) || 0;
      const safeChg = Number(changePct) || 0;
      const safeThreshold = Number(config.threshold) || 0;

      switch (config.condition) {
        case 'price_above':
          isTriggered = safePrice > safeThreshold;
          message = `${config.symbol} above $${safeThreshold} (now $${safePrice.toFixed(2)})`;
          break;
        case 'price_below':
          isTriggered = safePrice < safeThreshold;
          message = `${config.symbol} below $${safeThreshold} (now $${safePrice.toFixed(2)})`;
          break;
        case 'pct_change_above':
          isTriggered = safeChg > safeThreshold;
          message = `${config.symbol} up ${safeChg.toFixed(2)}% (threshold: ${safeThreshold}%)`;
          break;
        case 'pct_change_below':
          isTriggered = safeChg < -Math.abs(safeThreshold);
          message = `${config.symbol} down ${safeChg.toFixed(2)}% (threshold: -${Math.abs(safeThreshold)}%)`;
          break;
      }

      if (isTriggered) {
        triggered.push({
          id: `custom_${config.id}_${Math.floor(Date.now() / 300000)}`,
          type: 'custom_alert',
          severity: 'high',
          symbol: config.symbol,
          message,
          timestamp: Date.now(),
          configId: config.id,
        });
      }
    }
    return triggered;
  }, [configs]);

  return { configs, addConfig, removeConfig, toggleConfig, evaluateAlerts };
}

function getSymbolPrice(symbol: string, marketData: MarketSnapshot): number | null {
  const stock = marketData.stocks?.[symbol];
  if (stock?.price) return Number(stock.price);
  const crypto = marketData.crypto?.[symbol] || marketData.crypto?.[symbol + 'USDT'];
  if (crypto?.price) return Number(crypto.price);
  return null;
}

function getSymbolChangePct(symbol: string, marketData: MarketSnapshot): number {
  const stock = marketData.stocks?.[symbol];
  if (stock?.changePct != null) return Number(stock.changePct);
  const crypto = marketData.crypto?.[symbol] || marketData.crypto?.[symbol + 'USDT'];
  if (crypto?.changePct != null) return Number(crypto.changePct);
  return 0;
}
