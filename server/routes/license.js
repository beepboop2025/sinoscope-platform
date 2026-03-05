import { Router } from 'express';

const router = Router();

// POST /api/license/activate — validate an AppSumo or direct license code
router.post('/activate', async (req, res) => {
  const { code } = req.body;
  if (!code || typeof code !== 'string') {
    return res.status(400).json({ error: 'License code is required' });
  }

  const trimmed = code.trim().toUpperCase();
  if (trimmed.length < 8 || !/^[A-Z0-9]+$/.test(trimmed)) {
    return res.status(400).json({ error: 'Invalid license code format' });
  }

  // TODO: Validate against AppSumo API when ready:
  // POST https://appsumo.com/openapi/v1/validate_license/
  // Headers: { Authorization: `Bearer ${APPSUMO_API_KEY}` }
  // Body: { license_key: trimmed }
  //
  // For now, accept valid-format codes and log activation.
  // Replace this with real AppSumo validation before launch.

  console.log(`[LICENSE] Activation: code=${trimmed.slice(0, 4)}****`);

  res.json({
    valid: true,
    plan: 'pro',
    activatedAt: new Date().toISOString(),
  });
});

export default router;
