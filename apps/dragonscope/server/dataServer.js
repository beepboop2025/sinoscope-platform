#!/usr/bin/env node
/**
 * Lightweight HTTP server that serves collector JSON data files.
 * Runs on port 3456, CORS-enabled for local dev.
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.DATA_SERVER_PORT || 3456;
const DATA_DIR = path.join(__dirname, 'data');

const server = http.createServer((req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method !== 'GET') {
    res.writeHead(405, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Method not allowed' }));
    return;
  }

  // Parse URL — expect /{category}.json
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const filename = path.basename(url.pathname);

  // Only serve .json files, prevent directory traversal
  if (!filename.endsWith('.json') || filename.includes('..')) {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Invalid request' }));
    return;
  }

  const filePath = path.join(DATA_DIR, filename);

  fs.readFile(filePath, 'utf8', (err, content) => {
    if (err) {
      if (err.code === 'ENOENT') {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not found' }));
      } else {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Read error' }));
      }
      return;
    }

    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=10',
    });
    res.end(content);
  });
});

server.listen(PORT, () => {
  console.log(`[DataServer] Serving ${DATA_DIR} on http://localhost:${PORT}`);
});
