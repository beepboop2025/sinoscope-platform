#!/usr/bin/env node
import 'dotenv/config';
import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import path from 'path';
import { fileURLToPath } from 'url';
import { errorHandler } from './middleware/errorHandler.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Routes
import dataRoutes from './routes/data.js';
import portfolioRoutes from './routes/portfolios.js';
import watchlistRoutes from './routes/watchlists.js';
import alertRoutes from './routes/alerts.js';
import userRoutes from './routes/users.js';
import apiKeyRoutes from './routes/apiKeys.js';

const app = express();
const PORT = process.env.API_PORT || 3456;

// Middleware
app.use(helmet({ contentSecurityPolicy: false }));
app.use(cors({ origin: ['http://localhost:5174', 'http://127.0.0.1:5174', 'http://localhost:3456', 'http://127.0.0.1:3456'], credentials: true }));
app.use(compression());
app.use(express.json({ limit: '1mb' }));

// Rate limiting
app.use('/api', rateLimit({
  windowMs: 60 * 1000,
  max: 200,
  standardHeaders: true,
  legacyHeaders: false,
}));

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Routes
app.use('/api/data', dataRoutes);
app.use('/api/portfolios', portfolioRoutes);
app.use('/api/watchlists', watchlistRoutes);
app.use('/api/alerts', alertRoutes);
app.use('/api/users', userRoutes);
app.use('/api/api-keys', apiKeyRoutes);

// Backward compatibility: serve /{category}.json like old dataServer
app.get('/:file', (req, res, next) => {
  if (req.params.file.endsWith('.json')) {
    req.params.category = req.params.file.replace('.json', '');
    return dataRoutes.handle(req, res, next);
  }
  next();
});

// Production: serve built frontend
const distPath = path.join(__dirname, '..', 'dist');
app.use(express.static(distPath));
app.get('{*path}', (req, res, next) => {
  // Only serve index.html for non-API routes
  if (req.path.startsWith('/api/')) return next();
  res.sendFile(path.join(distPath, 'index.html'), (err) => {
    if (err) next();
  });
});

// Error handler
app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`[API Server] Running on http://localhost:${PORT}`);
});

export default app;
