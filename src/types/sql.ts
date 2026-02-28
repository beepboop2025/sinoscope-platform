export interface SqlQueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  executionTime: number;
  error?: string;
}

export interface SqlHistoryEntry {
  id: string;
  query: string;
  timestamp: number;
  rowCount: number;
  executionTime: number;
  error?: string;
}

export interface SavedQuery {
  id: string;
  name: string;
  query: string;
  description?: string;
  createdAt: number;
}

export interface SqlTableSchema {
  name: string;
  columns: SqlColumnSchema[];
  rowCount: number;
}

export interface SqlColumnSchema {
  name: string;
  type: string;
}

export interface SqlSchema {
  tables: SqlTableSchema[];
}
