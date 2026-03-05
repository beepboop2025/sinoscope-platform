import { useState, useCallback, type ReactElement, type ReactNode, type FormEvent } from 'react';
import { storageRead, storageWrite } from '../../utils/storage';

const LICENSE_KEY = 'dragonscope_license';

interface LicenseData {
  code: string;
  plan: string;
  activatedAt: number;
}

interface LicenseGateProps {
  children: ReactNode;
}

function isLicenseValid(): LicenseData | null {
  const data = storageRead<LicenseData>(LICENSE_KEY, null);
  if (!data || !data.code || !data.activatedAt) return null;
  return data;
}

async function validateLicense(code: string): Promise<{ valid: boolean; plan: string; error?: string }> {
  const trimmed = code.trim().toUpperCase();
  if (!trimmed || trimmed.length < 8) {
    return { valid: false, plan: '', error: 'Please enter a valid license code' };
  }

  try {
    const res = await fetch('/api/license/activate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: trimmed }),
    });

    if (res.ok) {
      const data = await res.json();
      return { valid: true, plan: data.plan || 'pro' };
    }

    // If backend is unavailable, do basic format validation as fallback
    if (res.status === 404 || res.status === 502) {
      // Backend not deployed yet — accept AppSumo format codes
      if (/^[A-Z0-9]{8,}$/.test(trimmed)) {
        return { valid: true, plan: 'pro' };
      }
    }

    const err = await res.json().catch(() => ({ error: 'Validation failed' }));
    return { valid: false, plan: '', error: err.error || 'Invalid license code' };
  } catch {
    // Network error — accept code format as fallback for offline activation
    if (/^[A-Z0-9]{8,}$/.test(trimmed)) {
      return { valid: true, plan: 'pro' };
    }
    return { valid: false, plan: '', error: 'Unable to validate. Check your internet connection.' };
  }
}

export default function LicenseGate({ children }: LicenseGateProps): ReactElement {
  const [license, setLicense] = useState<LicenseData | null>(() => isLicenseValid());
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleActivate = useCallback(async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await validateLicense(code);
    setLoading(false);

    if (result.valid) {
      const data: LicenseData = {
        code: code.trim().toUpperCase(),
        plan: result.plan,
        activatedAt: Date.now(),
      };
      storageWrite(LICENSE_KEY, data);
      setLicense(data);
    } else {
      setError(result.error || 'Invalid license code');
    }
  }, [code]);

  if (license) {
    return children as ReactElement;
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: '#050810', fontFamily: "'Outfit', sans-serif",
    }}>
      <div style={{
        background: '#0a0f1a', border: '1px solid #1a2338', borderRadius: 16,
        padding: 40, maxWidth: 440, width: '90vw', textAlign: 'center',
      }}>
        <div style={{ marginBottom: 24 }}>
          <span style={{ fontSize: 28, fontWeight: 700 }}>
            <span style={{ color: '#06d6e0' }}>Dragon</span>
            <span style={{ color: '#e2e8f0' }}>Scope</span>
          </span>
          <div style={{ fontSize: 12, color: '#4a5568', marginTop: 6, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Financial Terminal
          </div>
        </div>

        <h2 style={{ fontSize: 18, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>
          Activate Your License
        </h2>
        <p style={{ fontSize: 13, color: '#718096', marginBottom: 24, lineHeight: 1.5 }}>
          Enter your license code from AppSumo or dragonscope.io to get started.
        </p>

        <form onSubmit={handleActivate}>
          <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value)}
            placeholder="Enter license code (e.g. ABCD1234)"
            autoFocus
            style={{
              width: '100%', padding: '12px 16px', background: '#0f1628',
              border: '1px solid #1a2338', borderRadius: 8, color: '#e2e8f0',
              fontSize: 14, fontFamily: "'JetBrains Mono', monospace",
              outline: 'none', boxSizing: 'border-box', letterSpacing: '0.05em',
              textTransform: 'uppercase',
            }}
          />

          {error && (
            <div style={{ color: '#f56565', fontSize: 12, marginTop: 8, textAlign: 'left' }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !code.trim()}
            style={{
              width: '100%', marginTop: 16, padding: '12px 24px',
              background: loading ? '#1a2338' : '#06d6e0', color: loading ? '#718096' : '#050810',
              border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600,
              cursor: loading ? 'wait' : 'pointer', transition: 'all 0.2s',
            }}
          >
            {loading ? 'Validating...' : 'Activate License'}
          </button>
        </form>

        <div style={{ marginTop: 20, fontSize: 11, color: '#4a5568' }}>
          Don't have a license?{' '}
          <a
            href="https://dragonscope.io"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#06d6e0', textDecoration: 'none' }}
          >
            Purchase here
          </a>
        </div>
      </div>
    </div>
  );
}

export function useLicense(): LicenseData | null {
  return isLicenseValid();
}
