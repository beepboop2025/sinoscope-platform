import { useEffect } from 'react';
import { useSession, useUser } from '@clerk/clerk-react';
import { api } from '../../services/apiClient';

export default function ClerkSessionBridge({ children }) {
  const { session } = useSession();
  const { user } = useUser();

  // Expose session for apiClient.js to attach JWT tokens
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

  return children;
}
