/**
 * Correlation & Covariance Utilities
 * Pure functions for statistical analysis
 */

/**
 * Calculate Pearson correlation coefficient between two arrays
 * @param {Array<number>} x - First data series
 * @param {Array<number>} y - Second data series
 * @returns {number} Correlation coefficient (-1 to 1)
 */
export function pearsonCorrelation(x, y) {
  const n = x.length;
  if (n !== y.length || n === 0) return 0;
  
  const sumX = x.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
  const sumX2 = x.reduce((sum, xi) => sum + xi * xi, 0);
  const sumY2 = y.reduce((sum, yi) => sum + yi * yi, 0);
  
  const numerator = n * sumXY - sumX * sumY;
  const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  
  if (denominator === 0) return 0;
  return +(numerator / denominator).toFixed(4);
}

/**
 * Calculate covariance between two arrays
 * @param {Array<number>} x - First data series
 * @param {Array<number>} y - Second data series
 * @returns {number} Covariance
 */
export function covariance(x, y) {
  const n = x.length;
  if (n !== y.length || n === 0) return 0;
  
  const meanX = x.reduce((a, b) => a + b, 0) / n;
  const meanY = y.reduce((a, b) => a + b, 0) / n;
  
  return x.reduce((sum, xi, i) => sum + (xi - meanX) * (y[i] - meanY), 0) / (n - 1);
}

/**
 * Build correlation matrix from multiple data series
 * @param {Object} data - Object with symbol keys and value arrays
 * @returns {Object} Correlation matrix object
 */
export function buildCorrelationMatrix(data) {
  const symbols = Object.keys(data);
  const matrix = {};
  
  symbols.forEach(sym1 => {
    matrix[sym1] = {};
    symbols.forEach(sym2 => {
      if (sym1 === sym2) {
        matrix[sym1][sym2] = 1;
      } else {
        matrix[sym1][sym2] = pearsonCorrelation(data[sym1], data[sym2]);
      }
    });
  });
  
  return { symbols, matrix };
}

/**
 * Calculate rolling correlation with window
 * @param {Array<number>} x - First series
 * @param {Array<number>} y - Second series
 * @param {number} window - Window size
 * @returns {Array<number>} Rolling correlations
 */
export function rollingCorrelation(x, y, window = 30) {
  const result = [];
  for (let i = window; i <= x.length; i++) {
    const sliceX = x.slice(i - window, i);
    const sliceY = y.slice(i - window, i);
    result.push(pearsonCorrelation(sliceX, sliceY));
  }
  return result;
}

/**
 * Find highly correlated pairs from matrix
 * @param {Object} matrix - Correlation matrix
 * @param {number} threshold - Minimum correlation (default 0.8)
 * @returns {Array} List of correlated pairs
 */
export function findCorrelatedPairs(matrix, threshold = 0.8) {
  const pairs = [];
  const symbols = Object.keys(matrix);
  
  for (let i = 0; i < symbols.length; i++) {
    for (let j = i + 1; j < symbols.length; j++) {
      const corr = matrix[symbols[i]][symbols[j]];
      if (Math.abs(corr) >= threshold) {
        pairs.push({
          symbol1: symbols[i],
          symbol2: symbols[j],
          correlation: corr,
          relationship: corr > 0 ? 'positive' : 'negative',
        });
      }
    }
  }
  
  return pairs.sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation));
}

/**
 * Calculate variance of an array
 * @param {Array<number>} arr - Data array
 * @returns {number} Variance
 */
export function variance(arr) {
  const n = arr.length;
  if (n === 0) return 0;
  const mean = arr.reduce((a, b) => a + b, 0) / n;
  return arr.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / n;
}

/**
 * Calculate standard deviation
 * @param {Array<number>} arr - Data array
 * @returns {number} Standard deviation
 */
export function standardDeviation(arr) {
  return Math.sqrt(variance(arr));
}

/**
 * Calculate beta (correlation with market)
 * @param {Array<number>} stock - Stock returns
 * @param {Array<number>} market - Market returns
 * @returns {number} Beta coefficient
 */
export function calculateBeta(stock, market) {
  const stockVar = variance(stock);
  const marketVar = variance(market);
  const cov = covariance(stock, market);
  
  if (marketVar === 0) return 0;
  return cov / marketVar;
}

/**
 * Color scale for correlation heatmap
 * @param {number} value - Correlation value (-1 to 1)
 * @returns {string} CSS color
 */
export function correlationColor(value) {
  // Red (negative) to Blue (positive), white at 0
  if (value >= 0) {
    const intensity = Math.round(value * 255);
    return `rgb(${255 - intensity}, ${255 - intensity}, 255)`;
  } else {
    const intensity = Math.round(Math.abs(value) * 255);
    return `rgb(255, ${255 - intensity}, ${255 - intensity})`;
  }
}

export default {
  pearsonCorrelation,
  covariance,
  buildCorrelationMatrix,
  rollingCorrelation,
  findCorrelatedPairs,
  variance,
  standardDeviation,
  calculateBeta,
  correlationColor,
};
