/**
 * Feature flags for DragonScope.
 * With the enterprise backend, all data features are available
 * as long as the backend is reachable.
 */

interface FeatureFlags {
  /** Clerk authentication */
  hasAuth: boolean;
  /** Backend API URL is configured (production mode) */
  hasBackendUrl: boolean;
  /** Overall: always true in enterprise mode (backend provides all data) */
  isLiveMode: boolean;
}

export function getFeatureFlags(): FeatureFlags {
  const env = import.meta.env;
  const hasAuth = !!env.VITE_CLERK_PUBLISHABLE_KEY;
  const hasBackendUrl = !!env.VITE_API_BASE_URL;

  return {
    hasAuth,
    hasBackendUrl,
    isLiveMode: true, // Enterprise mode: backend always provides data
  };
}

/** Check if running in demo mode — always false in enterprise mode */
export function isDemoMode(): boolean {
  return false;
}
