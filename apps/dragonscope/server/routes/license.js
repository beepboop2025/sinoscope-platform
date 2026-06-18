import { Router } from 'express';
import rateLimit from 'express-rate-limit';

const router = Router();

// Rate limit: 10 attempts per 15 minutes per IP
const licenseRateLimit = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many license activation attempts. Please try again later.' },
});

// Known license prefixes (AppSumo codes typically start with these)
const VALID_PREFIXES = ['DS', 'DSCOPE', 'APPSUMO'];
const MIN_CODE_LENGTH = 8;
const MAX_CODE_LENGTH = 64;

function validateLicenseFormat(code) {
  if (!code || typeof code !== 'string') {
    return { valid: false, status: 400, error: 'License code is required' };
  }

  const trimmed = code.trim().toUpperCase();

  if (trimmed.length < MIN_CODE_LENGTH) {
    return { valid: false, status: 400, error: `License code must be at least ${MIN_CODE_LENGTH} characters` };
  }

  if (trimmed.length > MAX_CODE_LENGTH) {
    return { valid: false, status: 400, error: `License code must be at most ${MAX_CODE_LENGTH} characters` };
  }

  // Allow alphanumeric + hyphens (common in license keys)
  if (!/^[A-Z0-9-]+$/.test(trimmed)) {
    return { valid: false, status: 400, error: 'Invalid license code format: only alphanumeric characters and hyphens allowed' };
  }

  // Check for a known prefix
  const hasValidPrefix = VALID_PREFIXES.some(prefix => trimmed.startsWith(prefix));
  if (!hasValidPrefix) {
    return { valid: false, status: 403, error: 'Invalid license code: unrecognized prefix' };
  }

  return { valid: true, trimmed };
}

// POST /api/license/activate — validate an AppSumo or direct license code
router.post('/activate', licenseRateLimit, async (req, res) => {
  const { code } = req.body;

  const validation = validateLicenseFormat(code);
  if (!validation.valid) {
    return res.status(validation.status).json({ error: validation.error });
  }

  const { trimmed } = validation;

  // Validate against AppSumo API if configured
  const appSumoKey = process.env.APPSUMO_API_KEY;
  if (appSumoKey) {
    try {
      const response = await fetch('https://appsumo.com/openapi/v1/validate_license/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${appSumoKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ license_key: trimmed }),
      });

      if (!response.ok) {
        const status = response.status === 404 ? 403 : 502;
        console.warn(`[LICENSE] AppSumo validation failed: HTTP ${response.status} for code=${trimmed.slice(0, 4)}****`);
        return res.status(status).json({
          error: status === 403 ? 'Invalid license code' : 'License validation service unavailable',
        });
      }

      const data = await response.json();
      console.log(`[LICENSE] AppSumo validated: code=${trimmed.slice(0, 4)}**** plan=${data.plan || 'pro'}`);

      return res.json({
        valid: true,
        plan: data.plan || 'pro',
        activatedAt: new Date().toISOString(),
      });
    } catch (err) {
      console.error(`[LICENSE] AppSumo API error:`, err.message);
      return res.status(502).json({ error: 'License validation service unavailable' });
    }
  }

  // Fallback: no AppSumo API key configured — accept valid-format codes
  // This path should be replaced with real validation before launch
  console.warn(`[LICENSE] No APPSUMO_API_KEY configured — accepting valid-format code=${trimmed.slice(0, 4)}****`);

  res.json({
    valid: true,
    plan: 'pro',
    activatedAt: new Date().toISOString(),
  });
});

export default router;
