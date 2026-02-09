import { useState, useEffect, useCallback } from 'react';
import { storageRead, storageWrite } from '../utils/storage';

const STORAGE_KEY = 'dragonscope_portfolios';

// Uses localStorage for now; will integrate with API when backend is ready
export function usePortfolio() {
  const [portfolios, setPortfolios] = useState(() => storageRead(STORAGE_KEY, []));
  const [activeId, setActiveId] = useState(() => portfolios[0]?.id || null);

  useEffect(() => {
    storageWrite(STORAGE_KEY, portfolios);
  }, [portfolios]);

  const activePortfolio = portfolios.find(p => p.id === activeId) || portfolios[0] || null;

  const createPortfolio = useCallback((name) => {
    const newPortfolio = {
      id: 'pf_' + Date.now().toString(36),
      name,
      holdings: [],
      createdAt: Date.now(),
    };
    setPortfolios(prev => [...prev, newPortfolio]);
    setActiveId(newPortfolio.id);
    return newPortfolio;
  }, []);

  const deletePortfolio = useCallback((id) => {
    setPortfolios(prev => prev.filter(p => p.id !== id));
    setActiveId(prev => prev === id ? null : prev);
  }, []);

  const addHolding = useCallback((portfolioId, holding) => {
    setPortfolios(prev => prev.map(p => {
      if (p.id !== portfolioId) return p;
      return {
        ...p,
        holdings: [...p.holdings, {
          id: 'h_' + Date.now().toString(36),
          symbol: holding.symbol.toUpperCase(),
          assetType: holding.assetType || 'stock',
          quantity: Number(holding.quantity),
          avgCost: Number(holding.avgCost),
          notes: holding.notes || '',
          addedAt: Date.now(),
        }],
      };
    }));
  }, []);

  const removeHolding = useCallback((portfolioId, holdingId) => {
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
