import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  base: process.env.ELECTRON_BUILD ? './' : '/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@services': path.resolve(__dirname, './src/services'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@constants': path.resolve(__dirname, './src/constants'),
      '@engine': path.resolve(__dirname, './src/engine'),
      '@ml': path.resolve(__dirname, './src/ml'),
      '@generators': path.resolve(__dirname, './src/generators'),
      '@types': path.resolve(__dirname, './src/types'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-charts': ['lightweight-charts'],
          'vendor-data': ['alasql'],
          'vendor-ui': ['lucide-react', 'react-grid-layout'],
          'vendor-motion': ['framer-motion'],
          'vendor-state': ['zustand'],
          'vendor-cmdk': ['cmdk', 'sonner'],
          'vendor-viz': ['d3-hierarchy', 'canvas-confetti'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
    pool: 'threads',
    testTimeout: 10000,
    coverage: { provider: 'v8', include: ['src/**/*.{js,jsx,ts,tsx}'] },
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
      '/api/license': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/history': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/analytics': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/api/data-quality': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
        ws: true,
      },
      '/metrics': {
        target: 'http://127.0.0.1:3456',
        changeOrigin: true,
      },
    },
  },
})
