/**
 * LLM proxy route — lets the browser SPA use free LLM providers WITHOUT ever
 * seeing the API keys. Keys live in this server's env; the SPA only calls
 * POST /api/llm/chat. Authenticated (requireAuth) so it can't be used as an
 * open relay that drains the free quotas.
 */
import { Router } from 'express';
import rateLimit from 'express-rate-limit';
import { requireAuth } from '../middleware/auth.js';
import { getFreeRouter } from '../lib/free-llm-router.mjs';

const router = Router();
router.use(requireAuth);

// Tighter per-user limit than the global /api limiter — LLM calls are expensive
// against the free tiers, so cap them harder.
router.use(
  rateLimit({
    windowMs: 60_000,
    max: 20,
    keyGenerator: (req) => req.userId || req.ip,
    message: { error: 'LLM rate limit exceeded — try again shortly.' },
  }),
);

const MAX_MESSAGES = 30;
const MAX_CHARS = 24_000; // total prompt budget guard
const ALLOWED_TIERS = new Set(['fast', 'smart']);

router.post('/chat', async (req, res, next) => {
  try {
    const { messages, tier, taskType, temperature, maxTokens } = req.body ?? {};

    // ── validation ───────────────────────────────────────────────────────────
    if (!Array.isArray(messages) || messages.length === 0) {
      return res.status(400).json({ error: 'messages must be a non-empty array' });
    }
    if (messages.length > MAX_MESSAGES) {
      return res.status(400).json({ error: `too many messages (max ${MAX_MESSAGES})` });
    }
    let totalChars = 0;
    for (const m of messages) {
      if (!m || typeof m.content !== 'string' || !['system', 'user', 'assistant'].includes(m.role)) {
        return res.status(400).json({ error: 'each message needs role(system|user|assistant) + string content' });
      }
      totalChars += m.content.length;
    }
    if (totalChars > MAX_CHARS) {
      return res.status(413).json({ error: `prompt too large (max ${MAX_CHARS} chars)` });
    }
    if (tier !== undefined && !ALLOWED_TIERS.has(tier)) {
      return res.status(400).json({ error: 'tier must be "fast" or "smart"' });
    }

    const llm = getFreeRouter();
    if (!llm.hasProviders) {
      return res.status(503).json({ error: 'No free LLM providers configured on the server' });
    }

    const result = await llm.chatCompletion(messages, {
      tier,
      taskType,
      temperature: typeof temperature === 'number' ? temperature : undefined,
      // hard cap the output budget regardless of what the client asks for
      maxTokens: Math.min(Number(maxTokens) || 1024, 4096),
    });

    res.json(result);
  } catch (err) {
    // All providers failed → 502 (upstream), not a generic 500.
    if (String(err?.message || '').startsWith('No free provider served')) {
      return res.status(502).json({ error: 'All free LLM providers are currently unavailable' });
    }
    next(err);
  }
});

// Lightweight status for the SPA to show which providers are usable.
router.get('/providers', async (req, res) => {
  const llm = getFreeRouter();
  res.json({ enabled: llm.hasProviders });
});

export default router;
