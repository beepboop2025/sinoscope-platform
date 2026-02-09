import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-charts': ['recharts', 'lightweight-charts'],
          'vendor-data': ['alasql', 'xlsx'],
          'vendor-ui': ['lucide-react', 'react-grid-layout'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    pool: 'threads',
    testTimeout: 10000,
    coverage: { provider: 'v8', include: ['src/**/*.{js,jsx}'] },
  },
  server: {
    port: 5174,
    open: true,
    allowedHosts: ['host.docker.internal'],
    proxy: {
      '/api/yahoo': {
        target: 'https://query1.finance.yahoo.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/yahoo/, ''),
      },
      '/api/fred': {
        target: 'https://api.stlouisfed.org',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/fred/, ''),
      },
      '/api/rss': {
        target: 'https://api.rss2json.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/rss/, ''),
      },
      '/api/data': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/portfolios': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/watchlists': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/alerts': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/users': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/api-keys': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/health': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
    },
  },
})
