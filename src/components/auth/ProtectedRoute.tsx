import type { ReactElement, ReactNode } from 'react';
import { useAuth } from '@clerk/clerk-react';
import SignInPage from './SignInPage';

interface ProtectedRouteProps {
  children: ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps): ReactElement {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '100vh', background: 'var(--bg-0)', color: 'var(--text-3)',
      }}>
        Loading...
      </div>
    );
  }

  if (!isSignedIn) {
    return <SignInPage />;
  }

  return children as ReactElement;
}
