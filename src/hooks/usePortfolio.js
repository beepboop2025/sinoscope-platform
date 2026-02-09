import { useState, useEffect, useCallback, useRef } from 'react';
import { storageRead, storageWrite } from '../utils/storage';
import { api } from '../services/apiClient';

const STORAGE_KEY = 'dragonscope_portfolios';

export function usePortfolio() {
  const [portfolios, setPortfolios] = useState(() => storageRead(STORAGE_KEY, []));
  const [activeId, setActiveId] = useState(() => portfolios[0]?.id || null);
  const apiAvailable = useRef(false);

  // On mount: try loading from API, fall back to localStorage
  useEffect(() => {
    let cancelled = false;
    api.getPortfolios().then(data => {
      if (cancelled) return;
      apiAvailable.current = true;
      if (data && data.length >= 0) {
        // Normalize API response to match local shape
        const normalized = data.map(p => ({
          id: p.id,
          name: p.name,
          holdings: (p.holdings || []).map(h => ({
            id: h.id,
            symbol: h.symbol,
            assetType: h.assetType,
            quantity: h.quantity,
            avgCost: h.avgCost,
            notes: h.notes || '',
            addedAt: new Date(h.addedAt).getTime(),
          })),
          createdAt: new Date(p.createdAt).getTime(),
        }));
        setPortfolios(normalized);
        storageWrite(STORAGE_KEY, normalized);
      }
    }).catch(() => {
      // API unavailable — keep localStorage data
    });
    return () => { cancelled = true; };
  }, []);

  // Write-through to localStorage on every change
  useEffect(() => {
    storageWrite(STORAGE_KEY, portfolios);
  }, [portfolios]);

  const activePortfolio = portfolios.find(p => p.id === activeId) || portfolios[0] || null;

  const createPortfolio = useCallback(async (name) => {
    try {
      const created = await api.createPortfolio({ name });
      apiAvailable.current = true;
      const newPortfolio = {
        id: created.id,
        name: created.name,
        holdings: [],
        createdAt: new Date(created.createdAt).getTime(),
      };
      setPortfolios(prev => [...prev, newPortfolio]);
      setActiveId(newPortfolio.id);
      return newPortfolio;
    } catch {
      // Fallback: local-only
      const newPortfolio = {
        id: 'pf_' + Date.now().toString(36),
        name,
        holdings: [],
        createdAt: Date.now(),
      };
      setPortfolios(prev => [...prev, newPortfolio]);
      setActiveId(newPortfolio.id);
      return newPortfolio;
    }
  }, []);

  const deletePortfolio = useCallback(async (id) => {
    try {
      await api.deletePortfolio(id);
    } catch { /* local-only fallback */ }
    setPortfolios(prev => prev.filter(p => p.id !== id));
    setActiveId(prev => prev === id ? null : prev);
  }, []);

  const addHolding = useCallback(async (portfolioId, holding) => {
    const holdingData = {
      symbol: holding.symbol.toUpperCase(),
      assetType: holding.assetType || 'stock',
      quantity: Number(holding.quantity),
      avgCost: Number(holding.avgCost),
      notes: holding.notes || '',
    };

    try {
      const created = await api.addHolding(portfolioId, holdingData);
      setPortfolios(prev => prev.map(p => {
        if (p.id !== portfolioId) return p;
        return {
          ...p,
          holdings: [...p.holdings, {
            id: created.id,
            ...holdingData,
            addedAt: new Date(created.addedAt).getTime(),
          }],
        };
      }));
    } catch {
      // Local-only fallback
      setPortfolios(prev => prev.map(p => {
        if (p.id !== portfolioId) return p;
        return {
          ...p,
          holdings: [...p.holdings, {
            id: 'h_' + Date.now().toString(36),
            ...holdingData,
            addedAt: Date.now(),
          }],
        };
      }));
    }
  }, []);

  const removeHolding = useCallback(async (portfolioId, holdingId) => {
    try {
      await api.removeHolding(portfolioId, holdingId);
    } catch { /* local-only fallback */ }
    setPortfolios(prev => prev.map(p => {
      if (p.id !== portfolioId) return p;
      return { ...p, holdings: p.holdings.filter(h => h.id !== holdingId) };
    }));
  }, []);

  return {
    portfolios,
    activePortfolio,
    activeId,
    setActiveId,
    createPortfolio,
    deletePortfolio,
    addHolding,
    removeHolding,
  };
}
