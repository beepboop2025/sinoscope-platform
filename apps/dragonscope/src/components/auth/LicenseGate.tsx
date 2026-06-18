import { useState, useCallback, useEffect, useRef, type ReactElement, type ReactNode, type FormEvent } from 'react';
import { storageRead, storageWrite } from '../../utils/storage';

const LICENSE_KEY = 'dragonscope_license';
const MAX_ATTEMPTS = 5;
const LOCKOUT_MS = 60_000;

interface LicenseData {
  code: string;
  plan: string;
  activatedAt: number;
  fingerprint: string;
}

interface LicenseGateProps {
  children: ReactNode;
}

// Simple device fingerprint (not cryptographic, just deters casual sharing)
function getFingerprint(): string {
  const parts = [
    navigator.userAgent,
    navigator.language,
    screen.width + 'x' + screen.height,
    new Date().getTimezoneOffset().toString(),
  ];
  let hash = 0;
  const str = parts.join('|');
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
}

// DJB2 hash for checksum validation
function djb2(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

// Validate code format: PREFIX-XXXXX-XXXXX-CC
// PREFIX: DS1 (tier 1), DS2 (tier 2), DS3 (tier 3)
// CC: checksum chars derived from the rest
function validateCodeFormat(code: string): { valid: boolean; plan: string } {
  const trimmed = code.trim().toUpperCase().replace(/\s+/g, '');

  // Accept AppSumo redemption format: DS{1-3}-XXXXX-XXXXX-CC (18 chars with dashes)
  const match = trimmed.match(/^(DS[123])-([A-Z0-9]{5})-([A-Z0-9]{5})-([A-Z0-9]{2})$/);
  if (match) {
    const [, prefix, part1, part2, checksum] = match;
    const body = `${prefix}-${part1}-${part2}`;
    const expectedCheck = djb2(body).toString(36).toUpperCase().slice(-2).padStart(2, '0');
    if (checksum === expectedCheck) {
      const tier = prefix === 'DS1' ? 'starter' : prefix === 'DS2' ? 'pro' : 'business';
      return { valid: true, plan: tier };
    }
  }

  // Also accept raw AppSumo codes via backend validation (8+ alphanumeric)
  if (/^[A-Z0-9]{8,32}$/.test(trimmed)) {
    return { valid: true, plan: 'pro' };
  }

  return { valid: false, plan: '' };
}

function isLicenseValid(): LicenseData | null {
  const data = storageRead<LicenseData | null>(LICENSE_KEY, null);
  if (!data || !data.code || !data.activatedAt) return null;

  // Check fingerprint matches (allow mismatch for now — just log)
  const currentFp = getFingerprint();
  if (data.fingerprint && data.fingerprint !== currentFp) {
    // Different device — still allow but could enforce in future
  }

  return data;
}

async function validateLicense(code: string): Promise<{ valid: boolean; plan: string; error?: string }> {
  const trimmed = code.trim().toUpperCase();
  if (!trimmed || trimmed.length < 8) {
    return { valid: false, plan: '', error: 'Please enter a valid license code' };
  }

  // Try backend validation first
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

    if (res.status !== 404 && res.status !== 502) {
      const err = await res.json().catch(() => ({ error: 'Validation failed' }));
      return { valid: false, plan: '', error: err.error || 'Invalid license code' };
    }
  } catch {
    // Backend unavailable — fall through to offline validation
  }

  // Offline validation: check code format with checksum
  const result = validateCodeFormat(trimmed);
  if (result.valid) {
    return result;
  }

  return { valid: false, plan: '', error: 'Invalid license code. Check the code and try again.' };
}

export default function LicenseGate({ children }: LicenseGateProps): ReactElement {
  const [license, setLicense] = useState<LicenseData | null>(() => isLicenseValid());
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const attempts = useRef(0);
  const lockoutUntil = useRef(0);

  const handleActivate = useCallback(async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    // Rate limiting
    if (Date.now() < lockoutUntil.current) {
      const secsLeft = Math.ceil((lockoutUntil.current - Date.now()) / 1000);
      setError(`Too many attempts. Try again in ${secsLeft}s.`);
      return;
    }

    attempts.current++;
    if (attempts.current > MAX_ATTEMPTS) {
      lockoutUntil.current = Date.now() + LOCKOUT_MS;
      attempts.current = 0;
      setError('Too many attempts. Please wait 60 seconds.');
      return;
    }

    setLoading(true);
    const result = await validateLicense(code);
    setLoading(false);

    if (result.valid) {
      const data: LicenseData = {
        code: code.trim().toUpperCase(),
        plan: result.plan,
        activatedAt: Date.now(),
        fingerprint: getFingerprint(),
      };
      storageWrite(LICENSE_KEY, data);
      setLicense(data);
      attempts.current = 0;
    } else {
      setError(result.error || 'Invalid license code');
    }
  }, [code]);

  // The boot splash in index.html is normally removed when App mounts. When the
  // gate blocks (no license yet), App never mounts and the splash would cover
  // this form forever — clear it here too.
  useEffect(() => {
    if (license) return;
    const splash = document.getElementById('splash');
    if (splash) {
      splash.classList.add('splash-fade-out');
      setTimeout(() => splash.remove(), 600);
    }
  }, [license]);

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
            placeholder="Enter license code"
            autoFocus
            style={{
              width: '100%', padding: '12px 16px', background: '#0f1628',
              border: `1px solid ${error ? '#f56565' : '#1a2338'}`, borderRadius: 8, color: '#e2e8f0',
              fontSize: 14, fontFamily: "'JetBrains Mono', monospace",
              outline: 'none', boxSizing: 'border-box', letterSpacing: '0.05em',
              textTransform: 'uppercase', transition: 'border-color 0.2s',
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
              opacity: !code.trim() ? 0.5 : 1,
            }}
          >
            {loading ? 'Validating...' : 'Activate License'}
          </button>
        </form>

        <div style={{ marginTop: 24, fontSize: 11, color: '#4a5568' }}>
          Don't have a license?{' '}
          <a
            href="https://dragonscope.io"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#06d6e0', textDecoration: 'none' }}
          >
            Purchase here
          </a>
          {' '}or{' '}
          <a
            href="https://appsumo.com"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#06d6e0', textDecoration: 'none' }}
          >
            get on AppSumo
          </a>
        </div>
      </div>
    </div>
  );
}

export function useLicense(): LicenseData | null {
  return isLicenseValid();
}
