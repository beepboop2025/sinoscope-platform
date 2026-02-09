import { useState, useEffect, useCallback } from 'react';
import { storageRead, storageWrite } from '../utils/storage';

const STORAGE_KEY = 'dragonscope_alert_configs';

export function useAlertConfig() {
  const [configs, setConfigs] = useState(() => storageRead(STORAGE_KEY, []));

  useEffect(() => {
    storageWrite(STORAGE_KEY, configs);
  }, [configs]);

  const addConfig = useCallback((config) => {
    const threshold = Number(config.threshold);
    if (!Number.isFinite(threshold)) return;
    setConfigs(prev => [...prev, {
      id: 'ac_' + Date.now().toString(36),
      symbol: (config.symbol || '').toUpperCase(),
      condition: config.condition, // 'price_above', 'price_below', 'pct_change_above', 'pct_change_below'
      threshold,
      isActive: true,
      createdAt: Date.now(),
    }]);
  }, []);

  const removeConfig = useCallback((id) => {
    setConfigs(prev => prev.filter(c => c.id !== id));
  }, []);

  const toggleConfig = useCallback((id) => {
    setConfigs(prev => prev.map(c => c.id === id ? { ...c, isActive: !c.isActive } : c));
  }, []);

  const evaluateAlerts = useCallback((marketData) => {
    if (!marketData) return [];
    const triggered = [];

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

function getSymbolPrice(symbol, marketData) {
  const stock = marketData.stocks?.[symbol];
  if (stock?.price) return Number(stock.price);
  const crypto = marketData.crypto?.[symbol] || marketData.crypto?.[symbol + 'USDT'];
  if (crypto?.price) return Number(crypto.price);
  return null;
}

function getSymbolChangePct(symbol, marketData) {
  const stock = marketData.stocks?.[symbol];
  if (stock?.changePct != null) return Number(stock.changePct);
  const crypto = marketData.crypto?.[symbol] || marketData.crypto?.[symbol + 'USDT'];
  if (crypto?.changePct != null) return Number(crypto.changePct);
  return 0;
}
