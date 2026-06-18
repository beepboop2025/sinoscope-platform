const CACHE_VERSION = 'v3';
const STATIC_CACHE = `dragonscope-static-${CACHE_VERSION}`;
const API_DATA_CACHE = `dragonscope-api-${CACHE_VERSION}`;
const API_USER_CACHE = `dragonscope-user-${CACHE_VERSION}`;
const FONT_CACHE = `dragonscope-fonts-${CACHE_VERSION}`;
const ASSET_CACHE = `dragonscope-assets-${CACHE_VERSION}`;

const ALL_CACHES = [STATIC_CACHE, API_DATA_CACHE, API_USER_CACHE, FONT_CACHE, ASSET_CACHE];

const PRECACHE_URLS = ['/', '/index.html', '/favicon.svg', '/manifest.json'];

// User data endpoints — network-first (must be fresh, cached fallback)
const USER_API_PATTERNS = ['/api/portfolios', '/api/watchlists', '/api/alerts', '/api/users', '/api/api-keys'];

// Maximum age for cached API data (5 minutes)
const API_CACHE_MAX_AGE_MS = 5 * 60 * 1000;

// Install — precache static shell
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(PRECACHE_URLS))
  );
  // Don't call skipWaiting here — let the client control the update
});

// Activate — clean up old caches and notify clients of update
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => !ALL_CACHES.includes(k))
          .map(k => caches.delete(k))
      )
    ).then(() => {
      // Notify all clients that a new version is active
      return self.clients.matchAll().then(clients => {
        clients.forEach(client => {
          client.postMessage({ type: 'SW_UPDATED', version: CACHE_VERSION });
        });
      });
    })
  );
  self.clients.claim();
});

// Fetch — multi-strategy caching
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);

  // 1. Market data API — stale-while-revalidate (show cached instantly, refresh in background)
  if (url.pathname.startsWith('/api/data')) {
    e.respondWith(staleWhileRevalidate(e.request, API_DATA_CACHE));
    return;
  }

  // 2. User data API — network-first (must be fresh, cached fallback when offline)
  if (USER_API_PATTERNS.some(p => url.pathname.startsWith(p))) {
    e.respondWith(networkFirst(e.request, API_USER_CACHE));
    return;
  }

  // 3. Health check — network only
  if (url.pathname === '/api/health') {
    return;
  }

  // 4. Google Fonts — cache-first (immutable)
  if (url.hostname.includes('fonts.googleapis.com') || url.hostname.includes('fonts.gstatic.com')) {
    e.respondWith(cacheFirst(e.request, FONT_CACHE));
    return;
  }

  // 5. Built assets — cache-first (hashed filenames = immutable)
  if (url.pathname.startsWith('/assets/') || url.pathname.endsWith('.svg') || url.pathname.endsWith('.png')) {
    e.respondWith(cacheFirst(e.request, ASSET_CACHE));
    return;
  }

  // 6. HTML navigation — network-first
  if (e.request.mode === 'navigate' || e.request.headers.get('accept')?.includes('text/html')) {
    e.respondWith(networkFirst(e.request, STATIC_CACHE));
    return;
  }

  // 7. Everything else — cache-first with network fallback
  e.respondWith(cacheFirst(e.request, STATIC_CACHE));
});

// Message handler
self.addEventListener('message', (e) => {
  if (e.data === 'SKIP_WAITING' || e.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (e.data === 'CLEAR_CACHES') {
    caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))));
  }
  if (e.data === 'GET_VERSION') {
    e.source?.postMessage({ type: 'SW_VERSION', version: CACHE_VERSION });
  }
});

// --- Caching strategies ---

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response(JSON.stringify({ error: 'offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(() => null);

  return cached || (await fetchPromise) || new Response(JSON.stringify({ error: 'offline' }), {
    status: 503,
    headers: { 'Content-Type': 'application/json' },
  });
}
