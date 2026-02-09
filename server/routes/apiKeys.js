import { Router } from 'express';
import prisma from '../lib/prisma.js';
import { requireAuth } from '../middleware/auth.js';
import { hashApiKey } from '../lib/crypto.js';

const router = Router();
router.use(requireAuth);

router.get('/', async (req, res, next) => {
  try {
    const user = await prisma.user.findUnique({ where: { clerkId: req.userId } });
    if (!user) return res.status(404).json({ error: 'User not found' });
    const keys = await prisma.apiKey.findMany({
      where: { userId: user.id },
      select: { id: true, provider: true, label: true, createdAt: true },
    });
    res.json(keys);
  } catch (err) { next(err); }
});

router.post('/', async (req, res, next) => {
  try {
    const { provider, key, label } = req.body;
    if (!provider || !key) return res.status(400).json({ error: 'provider and key required' });
    const user = await prisma.user.findUnique({ where: { clerkId: req.userId } });
    if (!user) return res.status(404).json({ error: 'User not found' });
    const apiKey = await prisma.apiKey.upsert({
      where: { userId_provider: { userId: user.id, provider } },
      create: { userId: user.id, provider, keyHash: hashApiKey(key), label: label || provider },
      update: { keyHash: hashApiKey(key), label: label || provider },
    });
    res.status(201).json({ id: apiKey.id, provider: apiKey.provider, label: apiKey.label });
  } catch (err) { next(err); }
});

router.delete('/:id', async (req, res, next) => {
  try {
    await prisma.apiKey.delete({ where: { id: req.params.id } });
    res.status(204).end();
  } catch (err) { next(err); }
});

export default router;
