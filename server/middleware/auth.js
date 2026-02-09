// Clerk JWT verification middleware
// Will be fully implemented in Step 4; for now provides a stub
export function requireAuth(req, res, next) {
  // In development without Clerk, allow unauthenticated access
  if (process.env.NODE_ENV === 'development' && !process.env.CLERK_SECRET_KEY) {
    req.userId = 'dev-user';
    req.userEmail = 'dev@localhost';
    return next();
  }

  // Clerk auth will be added in Step 4
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // Placeholder - Step 4 will add real Clerk verification
  req.userId = 'dev-user';
  req.userEmail = 'dev@localhost';
  next();
}

export function optionalAuth(req, res, next) {
  const authHeader = req.headers.authorization;
  if (authHeader?.startsWith('Bearer ')) {
    req.userId = 'dev-user';
    req.userEmail = 'dev@localhost';
  }
  next();
}
