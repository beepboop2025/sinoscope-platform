/**
 * China Markets Constants
 * SSE/SZSE tickers, PBOC indicators, Belt & Road countries
 */

interface ChinaIndexEntry {
  readonly symbol: string;
  readonly name: string;
  readonly exchange: string;
  readonly currency: string;
  readonly timezone: string;
  readonly description?: string;
}

interface ChinaBlueChipEntry {
  readonly symbol: string;
  readonly name: string;
  readonly sector: string;
  readonly marketCap: string;
}

interface BRICountryEntry {
  readonly code: string;
  readonly name: string;
  readonly region: string;
  readonly joined: number;
  readonly projects: number;
  readonly flagship?: string;
}

interface BRICorridorEntry {
  readonly name: string;
  readonly route: string;
  readonly investment: string;
  readonly projects: number;
  readonly status: string;
}

interface PBOCToolEntry {
  readonly name: string;
  readonly description: string;
  readonly currentRate: number;
  readonly lastChange: string;
}

interface CNYMarketEntry {
  readonly symbol: string;
  readonly name: string;
  readonly tradedIn: string;
  readonly exchange: string;
  readonly tradingHours: string;
  readonly restrictions: string;
}

interface CNYSpreadInfo {
  readonly description: string;
  readonly normalRange: string;
  readonly positive: string;
  readonly negative: string;
}

interface ChinaCalendarEntry {
  readonly indicator: string;
  readonly frequency: string;
  readonly releaseDay: string;
  readonly importance: 'High' | 'Medium' | 'Low';
}

interface TradeCategoryItem {
  readonly category: string;
  readonly share: number;
  readonly examples: string;
}

// Major China Stock Indices
export const CHINA_INDICES: Record<string, ChinaIndexEntry> = {
  SSE: {
    symbol: '^SSEC',
    name: 'Shanghai Composite',
    exchange: 'SSE',
    currency: 'CNY',
    timezone: 'Asia/Shanghai',
  },
  SZSE: {
    symbol: '^SZSE',
    name: 'Shenzhen Component',
    exchange: 'SZSE',
    currency: 'CNY',
    timezone: 'Asia/Shanghai',
  },
  CSI300: {
    symbol: '000300.SS',
    name: 'CSI 300',
    exchange: 'SSE',
    currency: 'CNY',
    timezone: 'Asia/Shanghai',
    description: 'Top 300 A-shares',
  },
  HSI: {
    symbol: '^HSI',
    name: 'Hang Seng Index',
    exchange: 'HKEX',
    currency: 'HKD',
    timezone: 'Asia/Hong_Kong',
  },
  HSCE: {
    symbol: '^HSCE',
    name: 'Hang Seng China Enterprises',
    exchange: 'HKEX',
    currency: 'HKD',
    timezone: 'Asia/Hong_Kong',
    description: 'H-shares of mainland companies',
  },
  TECH: {
    symbol: '^HSTECH',
    name: 'Hang Seng Tech',
    exchange: 'HKEX',
    currency: 'HKD',
    timezone: 'Asia/Hong_Kong',
  },
} as const;

// Major A-Share Companies by Sector
export const CHINA_BLUE_CHIPS: Record<string, readonly ChinaBlueChipEntry[]> = {
  banks: [
    { symbol: '601398.SS', name: 'ICBC', sector: 'Banking', marketCap: '200B+' },
    { symbol: '601288.SS', name: 'Agricultural Bank', sector: 'Banking', marketCap: '150B+' },
    { symbol: '601939.SS', name: 'China Construction Bank', sector: 'Banking', marketCap: '180B+' },
    { symbol: '601988.SS', name: 'Bank of China', sector: 'Banking', marketCap: '130B+' },
  ],
  tech: [
    { symbol: '601012.SS', name: 'LONGi Green Energy', sector: 'Solar', marketCap: '30B' },
    { symbol: '002594.SZ', name: 'BYD', sector: 'EV', marketCap: '80B' },
    { symbol: '300750.SZ', name: 'CATL', sector: 'Batteries', marketCap: '90B' },
  ],
  consumer: [
    { symbol: '600519.SS', name: 'Kweichow Moutai', sector: 'Beverages', marketCap: '300B' },
    { symbol: '603288.SS', name: 'Foshan Haitian', sector: 'Food', marketCap: '40B' },
  ],
  energy: [
    { symbol: '601857.SS', name: 'PetroChina', sector: 'Oil & Gas', marketCap: '180B' },
    { symbol: '601088.SS', name: 'China Shenhua', sector: 'Coal', marketCap: '80B' },
  ],
} as const;

// Belt and Road Initiative Countries
export const BRI_COUNTRIES: readonly BRICountryEntry[] = [
  // East Asia
  { code: 'MNG', name: 'Mongolia', region: 'East Asia', joined: 2014, projects: 32 },
  // Southeast Asia
  { code: 'IDN', name: 'Indonesia', region: 'SE Asia', joined: 2013, projects: 89 },
  { code: 'MYS', name: 'Malaysia', region: 'SE Asia', joined: 2013, projects: 67 },
  { code: 'PHL', name: 'Philippines', region: 'SE Asia', joined: 2016, projects: 45 },
  { code: 'THA', name: 'Thailand', region: 'SE Asia', joined: 2013, projects: 78 },
  { code: 'VNM', name: 'Vietnam', region: 'SE Asia', joined: 2013, projects: 56 },
  { code: 'SGP', name: 'Singapore', region: 'SE Asia', joined: 2015, projects: 34 },
  { code: 'MMR', name: 'Myanmar', region: 'SE Asia', joined: 2014, projects: 42 },
  { code: 'KHM', name: 'Cambodia', region: 'SE Asia', joined: 2014, projects: 38 },
  { code: 'LAO', name: 'Laos', region: 'SE Asia', joined: 2013, projects: 67 },
  // South Asia
  { code: 'PAK', name: 'Pakistan', region: 'South Asia', joined: 2013, projects: 92, flagship: 'CPEC' },
  { code: 'BGD', name: 'Bangladesh', region: 'South Asia', joined: 2016, projects: 48 },
  { code: 'LKA', name: 'Sri Lanka', region: 'South Asia', joined: 2014, projects: 34 },
  { code: 'NPL', name: 'Nepal', region: 'South Asia', joined: 2017, projects: 23 },
  // Central Asia
  { code: 'KAZ', name: 'Kazakhstan', region: 'Central Asia', joined: 2013, projects: 56 },
  { code: 'UZB', name: 'Uzbekistan', region: 'Central Asia', joined: 2016, projects: 45 },
  { code: 'KGZ', name: 'Kyrgyzstan', region: 'Central Asia', joined: 2013, projects: 28 },
  { code: 'TJK', name: 'Tajikistan', region: 'Central Asia', joined: 2014, projects: 21 },
  // Middle East
  { code: 'ARE', name: 'UAE', region: 'Middle East', joined: 2014, projects: 54 },
  { code: 'SAU', name: 'Saudi Arabia', region: 'Middle East', joined: 2019, projects: 48 },
  { code: 'IRN', name: 'Iran', region: 'Middle East', joined: 2013, projects: 38 },
  { code: 'EGY', name: 'Egypt', region: 'Middle East', joined: 2016, projects: 42 },
  { code: 'TUR', name: 'Turkey', region: 'Middle East', joined: 2015, projects: 51 },
  // Europe
  { code: 'ITA', name: 'Italy', region: 'Europe', joined: 2019, projects: 34 },
  { code: 'GRC', name: 'Greece', region: 'Europe', joined: 2018, projects: 28 },
  { code: 'POL', name: 'Poland', region: 'Europe', joined: 2015, projects: 31 },
  { code: 'HUN', name: 'Hungary', region: 'Europe', joined: 2015, projects: 24 },
  { code: 'RUS', name: 'Russia', region: 'Europe', joined: 2013, projects: 78 },
  // Africa
  { code: 'KEN', name: 'Kenya', region: 'Africa', joined: 2014, projects: 56, flagship: 'Mombasa-Nairobi Railway' },
  { code: 'ETH', name: 'Ethiopia', region: 'Africa', joined: 2015, projects: 42 },
  { code: 'ZAF', name: 'South Africa', region: 'Africa', joined: 2015, projects: 38 },
  { code: 'NGA', name: 'Nigeria', region: 'Africa', joined: 2018, projects: 45 },
] as const;

// BRI Economic Corridors
export const BRI_CORRIDORS: readonly BRICorridorEntry[] = [
  {
    name: 'China-Pakistan Economic Corridor (CPEC)',
    route: 'Kashgar → Gwadar',
    investment: '$62B',
    projects: 92,
    status: 'Active',
  },
  {
    name: 'New Eurasian Land Bridge',
    route: 'Lianyungang → Rotterdam',
    investment: '$12B',
    projects: 156,
    status: 'Active',
  },
  {
    name: 'China-Mongolia-Russia Corridor',
    route: 'Tianjin → Ulan Bator → Moscow',
    investment: '$8B',
    projects: 45,
    status: 'Active',
  },
  {
    name: 'China-Indochina Peninsula',
    route: 'Kunming → Singapore',
    investment: '$25B',
    projects: 89,
    status: 'Active',
  },
  {
    name: 'China-Myanmar Corridor',
    route: 'Kunming → Kyaukphyu',
    investment: '$10B',
    projects: 34,
    status: 'Developing',
  },
  {
    name: 'Bangladesh-China-India-Myanmar',
    route: 'Kunming \u2192 Kolkata',
    investment: '$22B',
    projects: 67,
    status: 'Planning',
  },
] as const;

// PBOC Policy Tools
export const PBOC_TOOLS: Record<string, PBOCToolEntry> = {
  MLF: {
    name: 'Medium-term Lending Facility',
    description: '1-year loans to banks',
    currentRate: 2.50,
    lastChange: '2023-08-15',
  },
  ReverseRepo: {
    name: '7-Day Reverse Repo',
    description: 'Short-term liquidity',
    currentRate: 1.80,
    lastChange: '2023-08-15',
  },
  LPR_1Y: {
    name: '1-Year Loan Prime Rate',
    description: 'Corporate lending benchmark',
    currentRate: 3.45,
    lastChange: '2024-02-20',
  },
  LPR_5Y: {
    name: '5-Year Loan Prime Rate',
    description: 'Mortgage benchmark',
    currentRate: 4.20,
    lastChange: '2024-02-20',
  },
  RRR: {
    name: 'Reserve Requirement Ratio',
    description: 'Major banks reserve ratio',
    currentRate: 10.0,
    lastChange: '2023-09-15',
  },
} as const;

// CNY/CNH Market Info
export const CNY_MARKET: {
  readonly onshore: CNYMarketEntry;
  readonly offshore: CNYMarketEntry;
  readonly spread: CNYSpreadInfo;
} = {
  onshore: {
    symbol: 'CNY',
    name: 'Chinese Yuan (Onshore)',
    tradedIn: 'Mainland China',
    exchange: 'CFETS',
    tradingHours: '09:30-11:30, 13:00-15:00 CST',
    restrictions: 'Capital controls apply',
  },
  offshore: {
    symbol: 'CNH',
    name: 'Chinese Yuan (Offshore)',
    tradedIn: 'Hong Kong, Singapore, London',
    exchange: 'CNH Market',
    tradingHours: '24 hours',
    restrictions: 'Freely tradable',
  },
  spread: {
    description: 'CNH - CNY spread indicates offshore sentiment',
    normalRange: '\u00b1200 bps',
    positive: 'Offshore yuan weaker (outflow pressure)',
    negative: 'Offshore yuan stronger (inflow demand)',
  },
} as const;

// China Economic Calendar - Key Releases
export const CHINA_CALENDAR: readonly ChinaCalendarEntry[] = [
  { indicator: 'PMI Manufacturing', frequency: 'Monthly', releaseDay: '1st of month', importance: 'High' },
  { indicator: 'PMI Non-Manufacturing', frequency: 'Monthly', releaseDay: '1st of month', importance: 'Medium' },
  { indicator: 'Trade Balance', frequency: 'Monthly', releaseDay: '8-10th of month', importance: 'High' },
  { indicator: 'CPI', frequency: 'Monthly', releaseDay: '9-10th of month', importance: 'High' },
  { indicator: 'PPI', frequency: 'Monthly', releaseDay: '9-10th of month', importance: 'Medium' },
  { indicator: 'FX Reserves', frequency: 'Monthly', releaseDay: '7th of month', importance: 'Medium' },
  { indicator: 'New Yuan Loans', frequency: 'Monthly', releaseDay: '10-15th of month', importance: 'High' },
  { indicator: 'M2 Money Supply', frequency: 'Monthly', releaseDay: '10-15th of month', importance: 'Medium' },
  { indicator: 'GDP', frequency: 'Quarterly', releaseDay: '15th after quarter', importance: 'High' },
  { indicator: 'Industrial Production', frequency: 'Monthly', releaseDay: '15th of month', importance: 'High' },
  { indicator: 'Retail Sales', frequency: 'Monthly', releaseDay: '15th of month', importance: 'Medium' },
  { indicator: 'Fixed Asset Investment', frequency: 'Monthly', releaseDay: '15th of month', importance: 'Medium' },
  { indicator: 'LPR', frequency: 'Monthly', releaseDay: '20th of month', importance: 'High' },
] as const;

// US-China Trade Categories
export const TRADE_CATEGORIES: {
  readonly exports: readonly TradeCategoryItem[];
  readonly imports: readonly TradeCategoryItem[];
} = {
  exports: [
    { category: 'Electronics', share: 25, examples: 'Phones, computers, semiconductors' },
    { category: 'Machinery', share: 18, examples: 'Computers, parts, equipment' },
    { category: 'Textiles', share: 12, examples: 'Clothing, fabrics' },
    { category: 'Furniture', share: 8, examples: 'Household goods' },
    { category: 'Toys', share: 6, examples: 'Games, sports equipment' },
  ],
  imports: [
    { category: 'Agriculture', share: 22, examples: 'Soybeans, pork, corn' },
    { category: 'Energy', share: 18, examples: 'LNG, crude oil' },
    { category: 'Semiconductors', share: 15, examples: 'Chips, components' },
    { category: 'Aircraft', share: 10, examples: 'Boeing planes' },
    { category: 'Vehicles', share: 8, examples: 'Cars, parts' },
  ],
} as const;

export default {
  CHINA_INDICES,
  CHINA_BLUE_CHIPS,
  BRI_COUNTRIES,
  BRI_CORRIDORS,
  PBOC_TOOLS,
  CNY_MARKET,
  CHINA_CALENDAR,
  TRADE_CATEGORIES,
};
