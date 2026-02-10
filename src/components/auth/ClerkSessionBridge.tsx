import { useEffect, type ReactElement } from 'react';
import { useSession, useUser } from '@clerk/clerk-react';
import { api } from '../../services/apiClient';
import type { ReactNode } from 'react';

interface ClerkSessionBridgeProps {
  children: ReactNode;
}

export default function ClerkSessionBridge({ children }: ClerkSessionBridgeProps): ReactElement {
  const { session } = useSession();
  const { user } = useUser();

  // Expose session for apiClient to attach JWT tokens
  useEffect(() => {
    window.__clerk_session = session || null;
    return () => { window.__clerk_session = null; };
  }, [session]);

  // Auto-sync user to backend on sign-in
  useEffect(() => {
    if (!session || !user) return;
    api.syncUser({
      email: user.primaryEmailAddress?.emailAddress,
      displayName: user.fullName || user.firstName,
      avatarUrl: user.imageUrl,
    }).catch(() => { /* backend may be unavailable */ });
  }, [session, user]);

  return children as ReactElement;
}
