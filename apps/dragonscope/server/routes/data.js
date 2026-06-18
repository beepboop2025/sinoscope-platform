import { Router } from 'express';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, '..', 'data');

const router = Router();

router.get('/:category', async (req, res) => {
  const { category } = req.params;
  const filename = `${category}.json`;

  if (filename.includes('..') || filename.includes('/')) {
    return res.status(400).json({ error: 'Invalid category' });
  }

  try {
    const filePath = path.join(DATA_DIR, filename);
    const content = await fs.readFile(filePath, 'utf8');
    res.setHeader('Cache-Control', 'public, max-age=10');
    res.json(JSON.parse(content));
  } catch (err) {
    if (err.code === 'ENOENT') {
      return res.status(404).json({ error: 'Not found' });
    }
    res.status(500).json({ error: 'Read error' });
  }
});

export default router;
