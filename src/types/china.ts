export interface ChinaIndex {
  symbol: string;
  name: string;
  english: string;
  exchange: string;
}

export interface ChinaBlueChip {
  symbol: string;
  name: string;
  sector: string;
}

export interface BRICountry {
  name: string;
  region: string;
  lat: number;
  lng: number;
  projects: number;
  investment: number;
  status: string;
}

export interface BRICorridor {
  name: string;
  countries: string[];
  investment: number;
  projects: number;
  type: string;
}

export interface PBOCTool {
  name: string;
  rate: number;
  description: string;
  lastUpdate: string;
}

export interface ChinaCalendarEntry {
  date: string;
  event: string;
  impact: 'high' | 'medium' | 'low';
  forecast?: string;
  previous?: string;
}

export interface ChinaTradeCategory {
  name: string;
  exports: number;
  imports: number;
  balance: number;
}
