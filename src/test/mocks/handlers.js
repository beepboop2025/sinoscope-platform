import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('https://api.frankfurter.dev/v1/latest', () => {
    return HttpResponse.json({
      base: 'USD',
      date: '2024-01-15',
      rates: { EUR: 0.92, GBP: 0.79, JPY: 148.5, CNY: 7.18, INR: 83.1 },
    });
  }),
  http.get('https://api.coingecko.com/api/v3/coins/markets', () => {
    return HttpResponse.json([
      { id: 'bitcoin', symbol: 'btc', name: 'Bitcoin', current_price: 43000, price_change_percentage_24h: 2.5, total_volume: 25000000000, market_cap: 840000000000 },
      { id: 'ethereum', symbol: 'eth', name: 'Ethereum', current_price: 2500, price_change_percentage_24h: -1.2, total_volume: 12000000000, market_cap: 300000000000 },
    ]);
  }),
  http.get('https://api.coingecko.com/api/v3/coins/:id/market_chart', ({ params }) => {
    const prices = Array.from({ length: 30 }, (_, i) => [Date.now() - (29 - i) * 86400000, 40000 + Math.random() * 5000]);
    return HttpResponse.json({ prices });
  }),
  http.get('/api/collector/:file', () => {
    return HttpResponse.json({ _updated: new Date().toISOString(), _source: 'mock', data: {} });
  }),
];
