import { Router } from 'express';
import prisma from '../lib/prisma.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.use(requireAuth);

router.get('/', async (req, res, next) => {
  try {
    const watchlists = await prisma.watchlist.findMany({
      where: { userId: req.userId },
      include: { items: true },
      orderBy: { createdAt: 'desc' },
    });
    res.json(watchlists);
  } catch (err) { next(err); }
});

router.post('/', async (req, res, next) => {
  try {
    const { name } = req.body;
    if (!name) return res.status(400).json({ error: 'Name required' });
    const watchlist = await prisma.watchlist.create({
      data: { userId: req.userId, name },
      include: { items: true },
    });
    res.status(201).json(watchlist);
  } catch (err) { next(err); }
});

router.post('/:id/items', async (req, res, next) => {
  try {
    const { symbol, assetType } = req.body;
    if (!symbol) return res.status(400).json({ error: 'Symbol required' });
    const item = await prisma.watchlistItem.create({
      data: { watchlistId: req.params.id, symbol: symbol.toUpperCase(), assetType: assetType || 'stock' },
    });
    res.status(201).json(item);
  } catch (err) { next(err); }
});

router.delete('/:id', async (req, res, next) => {
  try {
    await prisma.watchlist.delete({ where: { id: req.params.id, userId: req.userId } });
    res.status(204).end();
  } catch (err) { next(err); }
});

router.delete('/:watchlistId/items/:itemId', async (req, res, next) => {
  try {
    // Verify item belongs to user's watchlist before deleting
    const item = await prisma.watchlistItem.findFirst({
      where: { id: req.params.itemId, watchlist: { userId: req.userId } },
    });
    if (!item) return res.status(404).json({ error: 'Item not found' });
    await prisma.watchlistItem.delete({ where: { id: req.params.itemId } });
    res.status(204).end();
  } catch (err) { next(err); }
});

export default router;
