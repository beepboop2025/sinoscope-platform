import { StrictMode, Component } from 'react';
import { createRoot } from 'react-dom/client';
import { ClerkProvider } from '@clerk/clerk-react';
import { ToastProvider } from './components/shared/Toast';
import { ThemeProvider } from './components/shared/ThemeProvider';
import ClerkSessionBridge from './components/auth/ClerkSessionBridge';
import App from './App.jsx';
import './styles/index.css';

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

class RootErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) {
    console.error('[RootErrorBoundary]', error, info?.componentStack);
  }
  handleReload = () => { window.location.reload(); };
  handleClear = () => {
    this.setState({ error: null });
  };
  render() {
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
  <ThemeProvider>
    <ToastProvider>
      <App />
    </ToastProvider>
  </ThemeProvider>
);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <RootErrorBoundary>
      {CLERK_KEY ? (
        <ClerkProvider publishableKey={CLERK_KEY}>
          <ClerkSessionBridge>
            {AppTree}
          </ClerkSessionBridge>
        </ClerkProvider>
      ) : (
        AppTree
      )}
    </RootErrorBoundary>
  </StrictMode>,
);
