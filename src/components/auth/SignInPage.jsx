import { SignIn } from '@clerk/clerk-react';

export default function SignInPage() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: 'var(--bg-0)',
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ marginBottom: 24 }}>
          <span style={{ fontSize: 24, fontWeight: 700 }}>
            <span style={{ color: 'var(--cyan)' }}>Dragon</span>
            <span style={{ color: 'var(--text-1)' }}>Scope</span>
          </span>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>Financial Terminal</div>
        </div>
        <SignIn
          appearance={{
            variables: {
              colorPrimary: '#06d6e0',
              colorBackground: '#0a0f1a',
              colorText: '#e2e8f0',
              colorInputBackground: '#0f1628',
              colorInputText: '#e2e8f0',
            },
          }}
        />
      </div>
    </div>
  );
}
