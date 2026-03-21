import { StrictMode, Component, type ReactNode, type ErrorInfo } from 'react';
import { createRoot } from 'react-dom/client';
import { ClerkProvider } from '@clerk/clerk-react';
import { ToastProvider } from './components/shared/Toast';
import { ThemeProvider } from './components/shared/ThemeProvider';
import { SymbolProvider } from './contexts/SymbolContext';
import ClerkSessionBridge from './components/auth/ClerkSessionBridge';
import ProtectedRoute from './components/auth/ProtectedRoute';
import LicenseGate from './components/auth/LicenseGate';
import { installGlobalErrorHandlers, reportError } from './utils/errorReporter';
import App from './App';
import './styles/index.css';

// Install global error handlers for production monitoring
installGlobalErrorHandlers();

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

interface RootErrorBoundaryProps {
  children: ReactNode;
}

interface RootErrorBoundaryState {
  error: Error | null;
}

class RootErrorBoundary extends Component<RootErrorBoundaryProps, RootErrorBoundaryState> {
  constructor(props: RootErrorBoundaryProps) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error: Error): RootErrorBoundaryState { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[RootErrorBoundary]', error, info?.componentStack);
    reportError(error, 'RootErrorBoundary');
  }
  handleReload = (): void => { window.location.reload(); };
  handleClear = (): void => {
    this.setState({ error: null });
  };
  render(): ReactNode {
    if (this.state.error) {
      return (
        <div style={{ background: '#0a0a0a', color: '#e2e2e2', minHeight: '100vh', padding: 40, fontFamily: 'JetBrains Mono, monospace' }}>
          <h1 style={{ color: '#ff5555', fontSize: 20, marginBottom: 16 }}>DragonScope crashed</h1>
          <pre style={{ color: '#ff8888', fontSize: 13, whiteSpace: 'pre-wrap', marginBottom: 24, padding: 16, background: '#1a1a1a', borderRadius: 8, border: '1px solid #333' }}>
            {this.state.error.message}{'\n\n'}{this.state.error.stack}
          </pre>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={this.handleClear} style={{ padding: '8px 20px', background: '#333', color: '#fff', border: '1px solid #555', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
              Try Again
            </button>
            <button onClick={this.handleReload} style={{ padding: '8px 20px', background: '#1a4a1a', color: '#4ade80', border: '1px solid #2a6a2a', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
              Reload App
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const AppTree = (
  <LicenseGate>
    <ThemeProvider>
      <SymbolProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </SymbolProvider>
    </ThemeProvider>
  </LicenseGate>
);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RootErrorBoundary>
      {CLERK_KEY ? (
        <ClerkProvider publishableKey={CLERK_KEY}>
          <ClerkSessionBridge>
            <ProtectedRoute>
              {AppTree}
            </ProtectedRoute>
          </ClerkSessionBridge>
        </ClerkProvider>
      ) : (
        AppTree
      )}
    </RootErrorBoundary>
  </StrictMode>,
);

// ── Service Worker registration with update handling ─────────────────────────
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then(registration => {
      console.info('[SW] Registered successfully');

      // Check for updates every 60 seconds
      setInterval(() => registration.update(), 60_000);

      // Listen for new service worker waiting to activate
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        if (!newWorker) return;

        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            // New version available — show update banner
            showUpdateBanner(registration);
          }
        });
      });
    }).catch(err => {
      console.warn('[SW] Registration failed:', err);
    });

    // Listen for SW messages (e.g., SW_UPDATED after activation)
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data?.type === 'SW_UPDATED') {
        console.info('[SW] Updated to version', event.data.version);
      }
    });
  });
}

function showUpdateBanner(registration: ServiceWorkerRegistration): void {
  const banner = document.createElement('div');
  banner.style.cssText = `
    position: fixed; top: 0; left: 0; right: 0; z-index: 100000;
    display: flex; align-items: center; justify-content: center; gap: 12px;
    padding: 10px 20px; font-size: 13px; font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    color: #fff; background: rgba(59, 130, 246, 0.95);
    backdrop-filter: blur(8px);
  `;

  const label = document.createElement('span');
  label.textContent = 'New version available';
  banner.appendChild(label);

  const updateBtn = document.createElement('button');
  updateBtn.textContent = 'Update now';
  updateBtn.style.cssText = `
    padding: 4px 14px; background: #fff; color: #3b82f6; border: none;
    border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600;
  `;
  updateBtn.addEventListener('click', () => {
    registration.waiting?.postMessage('SKIP_WAITING');
    window.location.reload();
  });
  banner.appendChild(updateBtn);

  const dismissBtn = document.createElement('button');
  dismissBtn.textContent = 'Later';
  dismissBtn.style.cssText = `
    padding: 4px 10px; background: transparent; color: rgba(255,255,255,0.8);
    border: 1px solid rgba(255,255,255,0.3); border-radius: 4px; cursor: pointer; font-size: 12px;
  `;
  dismissBtn.addEventListener('click', () => {
    banner.remove();
  });
  banner.appendChild(dismissBtn);

  document.body.appendChild(banner);
}
