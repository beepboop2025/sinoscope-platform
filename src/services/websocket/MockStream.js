import { rand } from '../../utils/math';

let mockInterval = null;
const subscribers = new Map();

const MOCK_PRICES = {
  BTCUSDT: 67500, ETHUSDT: 3400, BNBUSDT: 580, SOLUSDT: 145,
  XRPUSDT: 0.62, ADAUSDT: 0.48, DOGEUSDT: 0.165, DOTUSDT: 7.2,
};

export function startMockStream(onTick) {
  if (mockInterval) return;

  mockInterval = setInterval(() => {
    for (const [symbol, base] of Object.entries(MOCK_PRICES)) {
      const change = rand(-0.005, 0.005);
      MOCK_PRICES[symbol] = +(base * (1 + change)).toFixed(symbol.includes('BTC') ? 2 : 4);

      onTick({
        symbol,
        price: MOCK_PRICES[symbol],
        change: +(MOCK_PRICES[symbol] - base).toFixed(4),
        changePct: +(change * 100).toFixed(2),
        volume: rand(100, 5000),
        high: +(MOCK_PRICES[symbol] * 1.02).toFixed(2),
        low: +(MOCK_PRICES[symbol] * 0.98).toFixed(2),
        timestamp: Date.now(),
        mock: true,
      });
    }
  }, 2000);
}

export function stopMockStream() {
  if (mockInterval) {
    clearInterval(mockInterval);
    mockInterval = null;
  }
}
