import { verifyToken } from '@clerk/express';
import prisma from '../lib/prisma.js';

const CLERK_SECRET_KEY = process.env.CLERK_SECRET_KEY;

async function resolveUser(clerkId, email) {
  const user = await prisma.user.upsert({
    where: { clerkId },
    create: {
      clerkId,
      email: email || `${clerkId}@local`,
      preferences: { create: {} },
    },
    update: {},
  });
  return user;
}

export async function requireAuth(req, res, next) {
  try {
    // Dev mode: no Clerk key configured
    if (!CLERK_SECRET_KEY) {
      const user = await resolveUser('dev-user', 'dev@localhost');
      req.userId = user.id;
      req.clerkId = 'dev-user';
      req.userEmail = 'dev@localhost';
      return next();
    }

    // Production: verify Clerk JWT
    const authHeader = req.headers.authorization;
    if (!authHeader?.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const token = authHeader.slice(7);
    const payload = await verifyToken(token, { secretKey: CLERK_SECRET_KEY });
    const clerkId = payload.sub;
    const email = payload.email || payload.email_addresses?.[0]?.email_address;

    const user = await resolveUser(clerkId, email);
    req.userId = user.id;
    req.clerkId = clerkId;
    req.userEmail = email;
    next();
  } catch (err) {
    if (err.reason === 'token-expired' || err.reason === 'token-invalid') {
      return res.status(401).json({ error: 'Invalid or expired token' });
    }
    next(err);
  }
}

export async function optionalAuth(req, res, next) {
  try {
    if (!CLERK_SECRET_KEY) {
      const user = await resolveUser('dev-user', 'dev@localhost');
      req.userId = user.id;
      req.clerkId = 'dev-user';
      req.userEmail = 'dev@localhost';
      return next();
    }

    const authHeader = req.headers.authorization;
    if (authHeader?.startsWith('Bearer ')) {
      const token = authHeader.slice(7);
      const payload = await verifyToken(token, { secretKey: CLERK_SECRET_KEY });
      const clerkId = payload.sub;
      const email = payload.email || payload.email_addresses?.[0]?.email_address;
      const user = await resolveUser(clerkId, email);
      req.userId = user.id;
      req.clerkId = clerkId;
      req.userEmail = email;
    }
    next();
  } catch {
    // Optional auth — proceed without user
    next();
  }
}
