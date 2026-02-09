import { Router } from 'express';
import prisma from '../lib/prisma.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.use(requireAuth);

router.get('/me', async (req, res, next) => {
  try {
    let user = await prisma.user.findUnique({
      where: { clerkId: req.userId },
      include: { preferences: true },
    });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json(user);
  } catch (err) { next(err); }
});

router.post('/sync', async (req, res, next) => {
  try {
    const { email, displayName, avatarUrl } = req.body;
    const user = await prisma.user.upsert({
      where: { clerkId: req.userId },
      create: {
        clerkId: req.userId,
        email: email || req.userEmail,
        displayName,
        avatarUrl,
        preferences: { create: {} },
      },
      update: {
        email: email || undefined,
        displayName: displayName || undefined,
        avatarUrl: avatarUrl || undefined,
      },
      include: { preferences: true },
    });
    res.json(user);
  } catch (err) { next(err); }
});

router.patch('/preferences', async (req, res, next) => {
  try {
    const { defaultWorkspace, theme, refreshInterval, notifications } = req.body;
    const user = await prisma.user.findUnique({ where: { clerkId: req.userId } });
    if (!user) return res.status(404).json({ error: 'User not found' });

    const prefs = await prisma.userPreference.upsert({
      where: { userId: user.id },
      create: {
        userId: user.id,
        ...(defaultWorkspace && { defaultWorkspace }),
        ...(theme && { theme }),
        ...(refreshInterval && { refreshInterval }),
        ...(notifications !== undefined && { notifications }),
      },
      update: {
        ...(defaultWorkspace && { defaultWorkspace }),
        ...(theme && { theme }),
        ...(refreshInterval && { refreshInterval }),
        ...(notifications !== undefined && { notifications }),
      },
    });
    res.json(prefs);
  } catch (err) { next(err); }
});

export default router;
