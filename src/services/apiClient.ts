import type { ApiFetchOptions, ApiClient, LlmChatResult } from '../types/api';

declare global {
  interface Window {
    __clerk_session?: { getToken(): Promise<string | null> };
  }
}

const API_BASE: string = (import.meta.env.VITE_API_BASE_URL || '') + '/api';
const DEFAULT_TIMEOUT_MS = 10_000;

async function apiFetch(path: string, options: ApiFetchOptions = {}): Promise<unknown> {
  const { method = 'GET', body, headers: extraHeaders = {}, timeoutMs = DEFAULT_TIMEOUT_MS } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };

  // Attach Clerk JWT if available (added in Step 4)
  if (typeof window !== 'undefined' && window.__clerk_session) {
    try {
      const token: string | null = await window.__clerk_session.getToken();
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch {
      console.warn('[apiClient] Failed to get auth token');
    }
  }

  // AbortController-based timeout for all requests
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res: Response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      signal: controller.signal,
      ...(body ? { body: JSON.stringify(body) } : {}),
    });

    if (res.status === 204) return null;

    const data: unknown = await res.json();
    if (!res.ok) throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
    return data;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error(`Request to ${path} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api: ApiClient = {
  // Users
  getMe: () => apiFetch('/users/me'),
  syncUser: (data: unknown) => apiFetch('/users/sync', { method: 'POST', body: data }),
  updatePreferences: (prefs: unknown) => apiFetch('/users/preferences', { method: 'PATCH', body: prefs }),

  // Portfolios
  getPortfolios: () => apiFetch('/portfolios'),
  createPortfolio: (data: unknown) => apiFetch('/portfolios', { method: 'POST', body: data }),
  updatePortfolio: (id: string, data: unknown) => apiFetch(`/portfolios/${id}`, { method: 'PATCH', body: data }),
  deletePortfolio: (id: string) => apiFetch(`/portfolios/${id}`, { method: 'DELETE' }),
  addHolding: (portfolioId: string, data: unknown) => apiFetch(`/portfolios/${portfolioId}/holdings`, { method: 'POST', body: data }),
  removeHolding: (portfolioId: string, holdingId: string) => apiFetch(`/portfolios/${portfolioId}/holdings/${holdingId}`, { method: 'DELETE' }),

  // Watchlists
  getWatchlists: () => apiFetch('/watchlists'),
  createWatchlist: (data: unknown) => apiFetch('/watchlists', { method: 'POST', body: data }),
  deleteWatchlist: (id: string) => apiFetch(`/watchlists/${id}`, { method: 'DELETE' }),
  addWatchlistItem: (watchlistId: string, data: unknown) => apiFetch(`/watchlists/${watchlistId}/items`, { method: 'POST', body: data }),
  removeWatchlistItem: (watchlistId: string, itemId: string) => apiFetch(`/watchlists/${watchlistId}/items/${itemId}`, { method: 'DELETE' }),

  // Alerts
  getAlerts: () => apiFetch('/alerts'),
  createAlert: (data: unknown) => apiFetch('/alerts', { method: 'POST', body: data }),
  updateAlert: (id: string, data: unknown) => apiFetch(`/alerts/${id}`, { method: 'PATCH', body: data }),
  deleteAlert: (id: string) => apiFetch(`/alerts/${id}`, { method: 'DELETE' }),

  // API Keys
  getApiKeys: () => apiFetch('/api-keys'),
  saveApiKey: (data: unknown) => apiFetch('/api-keys', { method: 'POST', body: data }),
  deleteApiKey: (id: string) => apiFetch(`/api-keys/${id}`, { method: 'DELETE' }),

  // Data (backward compat)
  getData: (category: string) => apiFetch(`/data/${category}`),

  // History
  getHistoryCandles: (symbol: string, params: { interval?: string; start?: string; end?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.interval) qs.set('interval', params.interval);
    if (params.start) qs.set('start', params.start);
    if (params.end) qs.set('end', params.end);
    if (params.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return apiFetch(`/history/candles/${encodeURIComponent(symbol)}${q ? `?${q}` : ''}`);
  },
  getHistoryTicks: (symbol: string, params: { start?: string; end?: string; category?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.start) qs.set('start', params.start);
    if (params.end) qs.set('end', params.end);
    if (params.category) qs.set('category', params.category);
    if (params.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return apiFetch(`/history/ticks/${encodeURIComponent(symbol)}${q ? `?${q}` : ''}`);
  },
  getHistorySymbols: (category?: string) => {
    const q = category ? `?category=${encodeURIComponent(category)}` : '';
    return apiFetch(`/history/symbols${q}`);
  },

  // Analytics
  getCorrelations: (params: { days?: number; interval?: string; symbols?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.days) qs.set('days', String(params.days));
    if (params.interval) qs.set('interval', params.interval);
    if (params.symbols) qs.set('symbols', params.symbols);
    const q = qs.toString();
    return apiFetch(`/analytics/correlations${q ? `?${q}` : ''}`);
  },
  getPortfolioAnalytics: (portfolioId: string) => apiFetch(`/portfolios/${portfolioId}/analytics`),

  // Data Quality
  getDataQuality: () => apiFetch('/data-quality'),

  // LLM — free-provider router behind the authed backend proxy. Keys never
  // touch the browser; this just POSTs the prompt and gets the completion back.
  llmChat: (req) =>
    apiFetch('/llm/chat', { method: 'POST', body: req, timeoutMs: 45_000 }) as Promise<LlmChatResult>,
};
