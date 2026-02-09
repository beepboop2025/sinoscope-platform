const API_BASE = '/api';

async function apiFetch(path, options = {}) {
  const { method = 'GET', body, headers: extraHeaders = {} } = options;

  const headers = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };

  // Attach Clerk JWT if available (added in Step 4)
  if (typeof window !== 'undefined' && window.__clerk_session) {
    try {
      const token = await window.__clerk_session.getToken();
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch { /* no auth */ }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    ...(body && { body: JSON.stringify(body) }),
  });

  if (res.status === 204) return null;

  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export const api = {
  // Users
  getMe: () => apiFetch('/users/me'),
  syncUser: (data) => apiFetch('/users/sync', { method: 'POST', body: data }),
  updatePreferences: (prefs) => apiFetch('/users/preferences', { method: 'PATCH', body: prefs }),

  // Portfolios
  getPortfolios: () => apiFetch('/portfolios'),
  createPortfolio: (data) => apiFetch('/portfolios', { method: 'POST', body: data }),
  updatePortfolio: (id, data) => apiFetch(`/portfolios/${id}`, { method: 'PATCH', body: data }),
  deletePortfolio: (id) => apiFetch(`/portfolios/${id}`, { method: 'DELETE' }),
  addHolding: (portfolioId, data) => apiFetch(`/portfolios/${portfolioId}/holdings`, { method: 'POST', body: data }),
  removeHolding: (portfolioId, holdingId) => apiFetch(`/portfolios/${portfolioId}/holdings/${holdingId}`, { method: 'DELETE' }),

  // Watchlists
  getWatchlists: () => apiFetch('/watchlists'),
  createWatchlist: (data) => apiFetch('/watchlists', { method: 'POST', body: data }),
  deleteWatchlist: (id) => apiFetch(`/watchlists/${id}`, { method: 'DELETE' }),
  addWatchlistItem: (watchlistId, data) => apiFetch(`/watchlists/${watchlistId}/items`, { method: 'POST', body: data }),
  removeWatchlistItem: (watchlistId, itemId) => apiFetch(`/watchlists/${watchlistId}/items/${itemId}`, { method: 'DELETE' }),

  // Alerts
  getAlerts: () => apiFetch('/alerts'),
  createAlert: (data) => apiFetch('/alerts', { method: 'POST', body: data }),
  updateAlert: (id, data) => apiFetch(`/alerts/${id}`, { method: 'PATCH', body: data }),
  deleteAlert: (id) => apiFetch(`/alerts/${id}`, { method: 'DELETE' }),

  // API Keys
  getApiKeys: () => apiFetch('/api-keys'),
  saveApiKey: (data) => apiFetch('/api-keys', { method: 'POST', body: data }),
  deleteApiKey: (id) => apiFetch(`/api-keys/${id}`, { method: 'DELETE' }),

  // Data (backward compat)
  getData: (category) => apiFetch(`/data/${category}`),
};
