import type { ApiFetchOptions, ApiClient } from '../types/api';

declare global {
  interface Window {
    __clerk_session?: { getToken(): Promise<string | null> };
  }
}

const API_BASE: string = '/api';

async function apiFetch(path: string, options: ApiFetchOptions = {}): Promise<unknown> {
  const { method = 'GET', body, headers: extraHeaders = {} } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };

  // Attach Clerk JWT if available (added in Step 4)
  if (typeof window !== 'undefined' && window.__clerk_session) {
    try {
      const token: string | null = await window.__clerk_session.getToken();
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch { /* no auth */ }
  }

  const res: Response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    ...(body && { body: JSON.stringify(body) }),
  });

  if (res.status === 204) return null;

  const data: unknown = await res.json();
  if (!res.ok) throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
  return data;
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
};
