import { cacheGet, cacheSet } from '../CacheManager';
import { canRequest, consumeToken, createRateLimiter } from '../RateLimiter';

createRateLimiter('npm', 15, 60000);
createRateLimiter('pypi', 15, 60000);

const NPM_FINANCE_PACKAGES = [
  'ccxt', 'technicalindicators', 'yahoo-finance2', 'trading-signals',
  'lightweight-charts', 'stockfish', 'node-binance-api', 'tulind',
  'alpaca-trade-api', 'bitmex-realtime-api',
];

const PYPI_FINANCE_PACKAGES = [
  'yfinance', 'ccxt', 'pandas-ta', 'backtrader', 'zipline-reloaded',
  'alpaca-trade-api', 'freqtrade', 'ta-lib', 'pyalgotrade', 'vectorbt',
  'quantlib', 'arch', 'statsmodels', 'scipy', 'empyrical',
];

export async function fetchNpmPackageStats(packageName) {
  const cacheKey = `npm_${packageName}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('npm')) return null;
  consumeToken('npm');

  try {
    // Get download counts
    const dlRes = await fetch(`https://api.npmjs.org/downloads/point/last-week/${packageName}`);
    if (!dlRes.ok) return null;
    const dlData = await dlRes.json();

    // Get package info
    const infoRes = await fetch(`https://registry.npmjs.org/${packageName}/latest`);
    const info = infoRes.ok ? await infoRes.json() : {};

    const result = {
      name: packageName,
      registry: 'npm',
      weeklyDownloads: dlData.downloads || 0,
      version: info.version || '',
      description: (info.description || '').slice(0, 150),
      license: info.license || '',
    };

    cacheSet(cacheKey, result, 600000);
    return result;
  } catch (err) {
    console.warn('[NPM]', packageName, err.message);
    return null;
  }
}

export async function fetchPypiPackageStats(packageName) {
  const cacheKey = `pypi_${packageName}`;
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  if (!canRequest('pypi')) return null;
  consumeToken('pypi');

  try {
    const res = await fetch(`https://pypi.org/pypi/${packageName}/json`);
    if (!res.ok) return null;
    const data = await res.json();
    const info = data.info || {};

    const result = {
      name: packageName,
      registry: 'pypi',
      weeklyDownloads: 0, // PyPI doesn't expose this directly
      version: info.version || '',
      description: (info.summary || '').slice(0, 150),
      license: info.license || '',
      homePage: info.home_page || info.project_url || '',
    };

    cacheSet(cacheKey, result, 600000);
    return result;
  } catch (err) {
    console.warn('[PyPI]', packageName, err.message);
    return null;
  }
}

export async function fetchAllPackageStats() {
  const cacheKey = 'package_stats_all';
  const cached = cacheGet(cacheKey);
  if (cached) return cached;

  const results = [];

  // Fetch NPM packages
  for (const pkg of NPM_FINANCE_PACKAGES) {
    const stats = await fetchNpmPackageStats(pkg);
    if (stats) results.push(stats);
    await new Promise(r => setTimeout(r, 200));
  }

  // Fetch PyPI packages
  for (const pkg of PYPI_FINANCE_PACKAGES) {
    const stats = await fetchPypiPackageStats(pkg);
    if (stats) results.push(stats);
    await new Promise(r => setTimeout(r, 200));
  }

  // Sort NPM by downloads, PyPI by name
  results.sort((a, b) => b.weeklyDownloads - a.weeklyDownloads || a.name.localeCompare(b.name));

  if (results.length > 0) {
    cacheSet(cacheKey, results, 600000);
  }
  return results.length > 0 ? results : null;
}

export function getMockPackageStats() {
  return [
    { name: 'ccxt', registry: 'npm', weeklyDownloads: 185000, version: '4.4.8', description: 'CryptoCurrency eXchange Trading Library', license: 'MIT' },
    { name: 'yfinance', registry: 'pypi', weeklyDownloads: 0, version: '0.2.36', description: 'Download market data from Yahoo! Finance API', license: 'Apache-2.0' },
    { name: 'lightweight-charts', registry: 'npm', weeklyDownloads: 120000, version: '4.2.0', description: 'Performant financial charts built with HTML5 canvas', license: 'Apache-2.0' },
    { name: 'technicalindicators', registry: 'npm', weeklyDownloads: 45000, version: '3.1.0', description: 'Technical indicators written in JavaScript', license: 'MIT' },
    { name: 'pandas-ta', registry: 'pypi', weeklyDownloads: 0, version: '0.3.14b', description: 'Technical Analysis Library for Python 3', license: 'MIT' },
    { name: 'backtrader', registry: 'pypi', weeklyDownloads: 0, version: '1.9.78', description: 'BackTesting Engine', license: 'GPL-3.0' },
    { name: 'yahoo-finance2', registry: 'npm', weeklyDownloads: 32000, version: '2.11.0', description: 'Yahoo Finance API for Node.js', license: 'MIT' },
    { name: 'vectorbt', registry: 'pypi', weeklyDownloads: 0, version: '0.26.2', description: 'Find trading patterns with backtesting', license: 'Free' },
    { name: 'alpaca-trade-api', registry: 'npm', weeklyDownloads: 8000, version: '3.0.1', description: 'Alpaca Trading API client', license: 'Apache-2.0' },
    { name: 'quantlib', registry: 'pypi', weeklyDownloads: 0, version: '1.33', description: 'Python wrapper for the QuantLib library', license: 'BSD' },
  ];
}
