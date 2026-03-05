#!/usr/bin/env node
/**
 * Generate DragonScope license codes for AppSumo distribution.
 *
 * Usage: node scripts/generate-licenses.js [tier] [count]
 *   tier:  1 (starter), 2 (pro), 3 (business)  — default: 2
 *   count: number of codes to generate          — default: 10
 *
 * Format: DS{tier}-XXXXX-XXXXX-CC
 *   DS{1-3} = tier prefix
 *   XXXXX   = random alphanumeric segments
 *   CC      = DJB2 checksum of the body
 */

function djb2(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function randomSegment(len = 5) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // No I/O/0/1 to avoid confusion
  let result = '';
  for (let i = 0; i < len; i++) {
    result += chars[Math.floor(Math.random() * chars.length)];
  }
  return result;
}

function generateCode(tier = 2) {
  const prefix = `DS${tier}`;
  const part1 = randomSegment(5);
  const part2 = randomSegment(5);
  const body = `${prefix}-${part1}-${part2}`;
  const checksum = djb2(body).toString(36).toUpperCase().slice(-2).padStart(2, '0');
  return `${body}-${checksum}`;
}

const tier = parseInt(process.argv[2]) || 2;
const count = parseInt(process.argv[3]) || 10;

if (tier < 1 || tier > 3) {
  console.error('Tier must be 1, 2, or 3');
  process.exit(1);
}

const tierNames = { 1: 'Starter', 2: 'Pro', 3: 'Business' };
console.log(`\nGenerating ${count} DragonScope ${tierNames[tier]} (Tier ${tier}) license codes:\n`);

for (let i = 0; i < count; i++) {
  console.log(generateCode(tier));
}

console.log(`\nFormat: DS${tier}-XXXXX-XXXXX-CC`);
console.log('Share these codes via AppSumo or your distribution channel.\n');
