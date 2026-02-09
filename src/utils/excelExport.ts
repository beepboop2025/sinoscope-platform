import * as XLSX from 'xlsx';

export function exportToXlsx(sheetName: string, headers: string[], rows: Record<string, unknown>[], filename: string = 'dragonscope-export.xlsx'): void {
  const data = [headers, ...rows.map(row => headers.map(h => row[h] ?? ''))];
  const ws = XLSX.utils.aoa_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  XLSX.writeFile(wb, filename);
}
