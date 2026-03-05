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
