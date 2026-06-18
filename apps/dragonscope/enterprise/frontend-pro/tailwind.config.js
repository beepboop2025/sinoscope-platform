/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#020617',
          900: '#0f172a',
          850: '#131c31',
          800: '#1e293b',
          750: '#253554',
          700: '#334155',
          650: '#3d4e68',
          600: '#475569',
          500: '#64748b',
          400: '#94a3b8',
          300: '#cbd5e1',
          200: '#e2e8f0',
          100: '#f1f5f9',
          50: '#f8fafc',
        },
        // Trading colors
        bid: '#10b981',
        ask: '#ef4444',
        up: '#10b981',
        down: '#ef4444',
        neutral: '#94a3b8',
      },
      fontFamily: {
        mono: ['SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', 'monospace'],
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      fontSize: {
        '2xs': '0.625rem', // 10px
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      animation: {
        'flash-green': 'flash-green 0.3s ease-out',
        'flash-red': 'flash-red 0.3s ease-out',
        'pulse-ring': 'pulse-ring 1s cubic-bezier(0, 0, 0.2, 1) infinite',
        'slide-in': 'slide-in 0.2s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
      },
      keyframes: {
        'flash-green': {
          '0%': { backgroundColor: 'rgba(16, 185, 129, 0.4)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'flash-red': {
          '0%': { backgroundColor: 'rgba(239, 68, 68, 0.4)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.8)', opacity: '1' },
          '100%': { transform: 'scale(2)', opacity: '0' },
        },
        'slide-in': {
          from: { transform: 'translateX(-100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
      transitionDuration: {
        '50': '50ms',
        '100': '100ms',
      },
      cursor: {
        'col-resize': 'col-resize',
        'row-resize': 'row-resize',
      },
      boxShadow: {
        'glow-green': '0 0 10px rgba(16, 185, 129, 0.3)',
        'glow-red': '0 0 10px rgba(239, 68, 68, 0.3)',
        'glow-blue': '0 0 10px rgba(59, 130, 246, 0.3)',
      },
    },
  },
  plugins: [],
}
