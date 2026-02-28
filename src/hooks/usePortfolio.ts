import { useState, useEffect, useCallback, useRef } from 'react';
import { storageRead, storageWrite } from '../utils/storage';
import { api } from '../services/apiClient';

const STORAGE_KEY = 'dragonscope_portfolios';

interface PortfolioHolding {
  id: string;
  symbol: string;
  assetType: string;
  quantity: number;
  avgCost: number;
  notes: string;
  addedAt: number;
}

interface LocalPortfolio {
  id: string;
  name: string;
  holdings: PortfolioHolding[];
  createdAt: number;
}

interface HoldingInput {
  symbol: string;
  assetType?: string;
  quantity: number | string;
  avgCost: number | string;
  notes?: string;
}

interface UsePortfolioReturn {
  portfolios: LocalPortfolio[];
  activePortfolio: LocalPortfolio | null;
  activeId: string | null;
  setActiveId: React.Dispatch<React.SetStateAction<string | null>>;
  createPortfolio: (name: string) => Promise<LocalPortfolio>;
  deletePortfolio: (id: string) => Promise<void>;
  addHolding: (portfolioId: string, holding: HoldingInput) => Promise<void>;
  removeHolding: (portfolioId: string, holdingId: string) => Promise<void>;
}

export function usePortfolio(): UsePortfolioReturn {
  const [portfolios, setPortfolios] = useState<LocalPortfolio[]>(() => storageRead<LocalPortfolio[]>(STORAGE_KEY, []));
  const [activeId, setActiveId] = useState<string | null>(() => portfolios[0]?.id || null);
  const apiAvailable = useRef<boolean>(false);

  // On mount: try loading from API, fall back to localStorage
  useEffect(() => {
    let cancelled = false;
    api.getPortfolios().then(data => {
      if (cancelled) return;
      apiAvailable.current = true;
      const arr = data as Record<string, unknown>[];
      if (arr && arr.length >= 0) {
        // Normalize API response to match local shape
        const normalized: LocalPortfolio[] = arr.map(p => ({
          id: p.id as string,
          name: p.name as string,
          holdings: ((p.holdings as Record<string, unknown>[]) || []).map(h => ({
            id: h.id as string,
            symbol: h.symbol as string,
            assetType: h.assetType as string,
            quantity: h.quantity as number,
            avgCost: h.avgCost as number,
            notes: (h.notes as string) || '',
            addedAt: new Date(h.addedAt as string | number).getTime(),
          })),
          createdAt: new Date(p.createdAt as string | number).getTime(),
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

  const createPortfolio = useCallback(async (name: string): Promise<LocalPortfolio> => {
    try {
      const created = await api.createPortfolio({ name }) as Record<string, unknown>;
      apiAvailable.current = true;
      const newPortfolio: LocalPortfolio = {
        id: created.id as string,
        name: created.name as string,
        holdings: [],
        createdAt: new Date(created.createdAt as string | number).getTime(),
      };
      setPortfolios(prev => [...prev, newPortfolio]);
      setActiveId(newPortfolio.id);
      return newPortfolio;
    } catch {
      // Fallback: local-only
      const newPortfolio: LocalPortfolio = {
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

  const deletePortfolio = useCallback(async (id: string): Promise<void> => {
    try {
      await api.deletePortfolio(id);
    } catch { /* local-only fallback */ }
    setPortfolios(prev => prev.filter(p => p.id !== id));
    setActiveId(prev => prev === id ? null : prev);
  }, []);

  const addHolding = useCallback(async (portfolioId: string, holding: HoldingInput): Promise<void> => {
    const holdingData = {
      symbol: holding.symbol.toUpperCase(),
      assetType: holding.assetType || 'stock',
      quantity: Number(holding.quantity),
      avgCost: Number(holding.avgCost),
      notes: holding.notes || '',
    };

    try {
      const created = await api.addHolding(portfolioId, holdingData) as Record<string, unknown>;
      setPortfolios(prev => prev.map(p => {
        if (p.id !== portfolioId) return p;
        return {
          ...p,
          holdings: [...p.holdings, {
            id: created.id as string,
            ...holdingData,
            addedAt: new Date(created.addedAt as string | number).getTime(),
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

  const removeHolding = useCallback(async (portfolioId: string, holdingId: string): Promise<void> => {
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
