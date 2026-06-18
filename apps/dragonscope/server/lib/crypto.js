import { createHash } from 'node:crypto';

export function hashApiKey(key) {
  return createHash('sha256').update(key).digest('hex');
}
