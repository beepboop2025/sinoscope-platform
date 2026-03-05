import { Router } from 'express';
import prisma from '../lib/prisma.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.use(requireAuth);

router.get('/', async (req, res, next) => {
  try {
    const alerts = await prisma.alert.findMany({
      where: { userId: req.userId },
      orderBy: { createdAt: 'desc' },
    });
    res.json(alerts);
  } catch (err) { next(err); }
});

router.post('/', async (req, res, next) => {
  try {
    const { symbol, condition, threshold } = req.body;
    if (!symbol || !condition || threshold == null) {
      return res.status(400).json({ error: 'symbol, condition, and threshold required' });
    }
    const VALID_CONDITIONS = ['above', 'below', 'crosses_above', 'crosses_below'];
    if (!VALID_CONDITIONS.includes(condition)) {
      return res.status(400).json({ error: `Invalid condition. Must be one of: ${VALID_CONDITIONS.join(', ')}` });
    }
    if (typeof symbol !== 'string' || symbol.length > 20 || !/^[A-Za-z0-9/._-]+$/.test(symbol)) {
      return res.status(400).json({ error: 'Invalid symbol format' });
    }
    if (isNaN(Number(threshold))) {
      return res.status(400).json({ error: 'threshold must be a number' });
    }
    const alert = await prisma.alert.create({
      data: {
        userId: req.userId,
        symbol: symbol.toUpperCase(),
        condition,
        threshold: Number(threshold),
      },
    });
    res.status(201).json(alert);
  } catch (err) { next(err); }
});

router.patch('/:id', async (req, res, next) => {
  try {
    const { isActive, condition, threshold } = req.body;
    const alert = await prisma.alert.update({
      where: { id: req.params.id, userId: req.userId },
      data: {
        ...(isActive !== undefined && { isActive }),
        ...(condition && { condition }),
        ...(threshold != null && { threshold: Number(threshold) }),
      },
    });
    res.json(alert);
  } catch (err) { next(err); }
});

router.delete('/:id', async (req, res, next) => {
  try {
    await prisma.alert.delete({ where: { id: req.params.id, userId: req.userId } });
    res.status(204).end();
  } catch (err) { next(err); }
});

export default router;
