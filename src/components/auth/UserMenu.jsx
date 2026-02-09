import { memo } from 'react';
import { UserButton, useUser } from '@clerk/clerk-react';

const UserMenu = memo(() => {
  const { user, isLoaded } = useUser();

  if (!isLoaded) return null;

  if (!user) {
    return (
      <span style={{ fontSize: 10, color: 'var(--text-4)' }}>Not signed in</span>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 10, color: 'var(--text-2)' }}>
        {user.firstName || user.emailAddresses?.[0]?.emailAddress || 'User'}
      </span>
      <UserButton
        appearance={{
          variables: {
            colorPrimary: '#06d6e0',
            colorBackground: '#0a0f1a',
            colorText: '#e2e8f0',
          },
        }}
      />
    </div>
  );
});
UserMenu.displayName = 'UserMenu';
export default UserMenu;
