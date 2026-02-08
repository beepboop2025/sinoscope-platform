import { rand } from '../utils/math';

export function generateMockEconomic() {
  return {
    GDP: { value: +(2.1 + rand(-0.5, 0.5)).toFixed(1), unit: '%', date: '2024-Q3' },
    CPI: { value: +(3.2 + rand(-0.3, 0.3)).toFixed(1), unit: '%', date: '2024-01' },
    UNEMPLOYMENT: { value: +(3.7 + rand(-0.2, 0.2)).toFixed(1), unit: '%', date: '2024-01' },
    FED_RATE: { value: 5.33, unit: '%', date: '2024-01' },
    PMI: { value: +(50.3 + rand(-2, 2)).toFixed(1), unit: 'Index', date: '2024-01' },
    RETAIL_SALES: { value: +(0.6 + rand(-0.4, 0.4)).toFixed(1), unit: '%', date: '2024-01' },
    TRADE_BALANCE: { value: +(-68.3 + rand(-5, 5)).toFixed(1), unit: '$B', date: '2024-01' },
  };
}

export function generateMockYieldCurve() {
  return [
    { maturity: '1M', yield: +(5.53 + rand(-0.05, 0.05)).toFixed(2) },
    { maturity: '3M', yield: +(5.48 + rand(-0.05, 0.05)).toFixed(2) },
    { maturity: '6M', yield: +(5.38 + rand(-0.05, 0.05)).toFixed(2) },
    { maturity: '1Y', yield: +(5.05 + rand(-0.05, 0.05)).toFixed(2) },
    { maturity: '2Y', yield: +(4.48 + rand(-0.08, 0.08)).toFixed(2) },
    { maturity: '3Y', yield: +(4.22 + rand(-0.08, 0.08)).toFixed(2) },
    { maturity: '5Y', yield: +(4.12 + rand(-0.08, 0.08)).toFixed(2) },
    { maturity: '7Y', yield: +(4.18 + rand(-0.08, 0.08)).toFixed(2) },
    { maturity: '10Y', yield: +(4.28 + rand(-0.08, 0.08)).toFixed(2) },
    { maturity: '20Y', yield: +(4.58 + rand(-0.08, 0.08)).toFixed(2) },
    { maturity: '30Y', yield: +(4.48 + rand(-0.08, 0.08)).toFixed(2) },
  ];
}
