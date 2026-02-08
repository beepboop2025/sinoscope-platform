import { rand } from '../utils/math';

export function generateMockChinaIndices() {
  return [
    { symbol: '^SSEC', name: 'Shanghai Composite', price: +(3088 + rand(-30, 30)).toFixed(2), change: +rand(-20, 20).toFixed(2), changesPercentage: +rand(-1, 1).toFixed(2) },
    { symbol: '000300.SS', name: 'CSI 300', price: +(3580 + rand(-40, 40)).toFixed(2), change: +rand(-25, 25).toFixed(2), changesPercentage: +rand(-1.2, 1.2).toFixed(2) },
    { symbol: '^HSI', name: 'Hang Seng', price: +(16800 + rand(-200, 200)).toFixed(2), change: +rand(-150, 150).toFixed(2), changesPercentage: +rand(-1.5, 1.5).toFixed(2) },
    { symbol: '^SZSE', name: 'Shenzhen Component', price: +(9650 + rand(-80, 80)).toFixed(2), change: +rand(-60, 60).toFixed(2), changesPercentage: +rand(-1, 1).toFixed(2) },
    { symbol: '^HSCE', name: 'Hang Seng China Enterprises', price: +(5680 + rand(-60, 60)).toFixed(2), change: +rand(-40, 40).toFixed(2), changesPercentage: +rand(-1.2, 1.2).toFixed(2) },
    { symbol: '^HSTECH', name: 'Hang Seng Tech', price: +(3520 + rand(-50, 50)).toFixed(2), change: +rand(-35, 35).toFixed(2), changesPercentage: +rand(-1.5, 1.5).toFixed(2) },
  ];
}

export function generateMockChinaStocks() {
  return [
    { symbol: '601398.SS', name: 'ICBC', price: +(5.12 + rand(-0.08, 0.08)).toFixed(2), change: +rand(-0.06, 0.06).toFixed(2), changesPercentage: +rand(-1.2, 1.2).toFixed(2) },
    { symbol: '002594.SZ', name: 'BYD', price: +(268 + rand(-5, 5)).toFixed(2), change: +rand(-4, 4).toFixed(2), changesPercentage: +rand(-1.5, 1.5).toFixed(2) },
    { symbol: '300750.SZ', name: 'CATL', price: +(196 + rand(-4, 4)).toFixed(2), change: +rand(-3, 3).toFixed(2), changesPercentage: +rand(-1.8, 1.8).toFixed(2) },
    { symbol: '600519.SS', name: 'Kweichow Moutai', price: +(1688 + rand(-20, 20)).toFixed(2), change: +rand(-15, 15).toFixed(2), changesPercentage: +rand(-1, 1).toFixed(2) },
    { symbol: '601857.SS', name: 'PetroChina', price: +(8.95 + rand(-0.12, 0.12)).toFixed(2), change: +rand(-0.10, 0.10).toFixed(2), changesPercentage: +rand(-1.1, 1.1).toFixed(2) },
    { symbol: '601939.SS', name: 'China Construction Bank', price: +(6.88 + rand(-0.08, 0.08)).toFixed(2), change: +rand(-0.06, 0.06).toFixed(2), changesPercentage: +rand(-0.9, 0.9).toFixed(2) },
  ];
}

export function generateMockCNYRates() {
  const cny = +(7.24 + rand(-0.03, 0.03)).toFixed(4);
  const cnh = +(cny + rand(-0.01, 0.02)).toFixed(4);
  return { cnyUsd: cny, cnhUsd: cnh, timestamp: Date.now() };
}
