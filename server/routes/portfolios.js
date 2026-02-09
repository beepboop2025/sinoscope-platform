import { Router } from 'express';
import prisma from '../lib/prisma.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.use(requireAuth);

// GET /api/portfolios
router.get('/', async (req, res, next) => {
  try {
    const portfolios = await prisma.portfolio.findMany({
      where: { userId: req.userId },
      include: { holdings: true },
      orderBy: { createdAt: 'desc' },
    });
    res.json(portfolios);
  } catch (err) { next(err); }
});

// POST /api/portfolios
router.post('/', async (req, res, next) => {
  try {
    const { name, description } = req.body;
    if (!name) return res.status(400).json({ error: 'Name required' });
    const portfolio = await prisma.portfolio.create({
      data: { userId: req.userId, name, description },
      include: { holdings: true },
    });
    res.status(201).json(portfolio);
  } catch (err) { next(err); }
});

// PATCH /api/portfolios/:id
router.patch('/:id', async (req, res, next) => {
  try {
    const { name, description } = req.body;
    const portfolio = await prisma.portfolio.update({
      where: { id: req.params.id, userId: req.userId },
      data: { ...(name && { name }), ...(description !== undefined && { description }) },
      include: { holdings: true },
    });
    res.json(portfolio);
  } catch (err) { next(err); }
});

// DELETE /api/portfolios/:id
router.delete('/:id', async (req, res, next) => {
  try {
    await prisma.portfolio.delete({ where: { id: req.params.id, userId: req.userId } });
    res.status(204).end();
  } catch (err) { next(err); }
});

// POST /api/portfolios/:id/holdings
router.post('/:id/holdings', async (req, res, next) => {
  try {
    const { symbol, assetType, quantity, avgCost, notes } = req.body;
    if (!symbol || !quantity || !avgCost) {
      return res.status(400).json({ error: 'symbol, quantity, and avgCost required' });
    }
    const holding = await prisma.holding.create({
      data: {
        portfolioId: req.params.id,
        symbol: symbol.toUpperCase(),
        assetType: assetType || 'stock',
        quantity: Number(quantity),
        avgCost: Number(avgCost),
        notes,
      },
    });
    res.status(201).json(holding);
  } catch (err) { next(err); }
});

// DELETE /api/portfolios/:portfolioId/holdings/:holdingId
router.delete('/:portfolioId/holdings/:holdingId', async (req, res, next) => {
  try {
    await prisma.holding.delete({ where: { id: req.params.holdingId } });
    res.status(204).end();
  } catch (err) { next(err); }
});

export default router;
