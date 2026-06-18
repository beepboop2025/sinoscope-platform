/**
 * VirtualTable — renders only visible rows for large datasets.
 * Uses translateY to position visible rows within a scrollable container.
 * Buffer of 5 rows above/below the viewport for smooth scrolling.
 */

import { useState, useRef, useCallback, useMemo, useEffect, memo, type ReactElement, type ReactNode, type CSSProperties, type KeyboardEvent, type UIEvent } from 'react';

export interface VirtualTableColumn<T extends Record<string, unknown> = Record<string, unknown>> {
  key: string;
  label: string;
  style?: CSSProperties;
  cellStyle?: CSSProperties;
  render?: (value: unknown, row: T) => ReactNode;
}

interface VirtualTableProps<T extends Record<string, unknown> = Record<string, unknown>> {
  columns: VirtualTableColumn<T>[];
  rows: T[];
  rowHeight?: number;
  containerHeight?: number;
  onRowClick?: (row: T) => void;
  /** Buffer rows above and below the viewport (default 5) */
  buffer?: number;
}

type SortDir = 'asc' | 'desc';

function VirtualTableInner<T extends Record<string, unknown>>({
  columns,
  rows,
  rowHeight = 28,
  containerHeight = 400,
  onRowClick,
  buffer = 5,
}: VirtualTableProps<T>): ReactElement {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleSort = useCallback((col: string): void => {
    setSortCol(prev => {
      if (prev === col) {
        setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        return col;
      }
      setSortDir('asc');
      return col;
    });
  }, []);

  const sorted = useMemo(() => {
    if (!sortCol) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol];
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av ?? '').localeCompare(String(bv ?? ''));
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rows, sortCol, sortDir]);

  const totalHeight = sorted.length * rowHeight;

  // Compute visible range with buffer
  const startIndex = useMemo(() => {
    return Math.max(0, Math.floor(scrollTop / rowHeight) - buffer);
  }, [scrollTop, rowHeight, buffer]);

  const endIndex = useMemo(() => {
    const visibleCount = Math.ceil(containerHeight / rowHeight);
    return Math.min(sorted.length, Math.floor(scrollTop / rowHeight) + visibleCount + buffer);
  }, [scrollTop, rowHeight, containerHeight, sorted.length, buffer]);

  const visibleRows = useMemo(() => {
    return sorted.slice(startIndex, endIndex);
  }, [sorted, startIndex, endIndex]);

  const offsetY = startIndex * rowHeight;

  const handleScroll = useCallback((e: UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const handleRowKeyDown = useCallback((e: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onRowClick(row);
    }
  }, [onRowClick]);

  const getAriaSortValue = (colKey: string): 'ascending' | 'descending' | undefined => {
    if (sortCol !== colKey) return undefined;
    return sortDir === 'asc' ? 'ascending' : 'descending';
  };

  // Header height (approx 28px for dense-table)
  const headerHeight = 28;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: containerHeight, minHeight: 0 }}>
      {/* Row count indicator */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '2px 6px', fontSize: 10, color: 'var(--text-4)', flexShrink: 0,
      }}>
        <span>{sorted.length.toLocaleString()} rows</span>
        <span>Showing {startIndex + 1}–{endIndex} of {sorted.length}</span>
      </div>

      {/* Sticky header + scrollable body */}
      <div style={{ flex: 1, minHeight: 0, position: 'relative', overflow: 'hidden' }}>
        {/* Fixed header */}
        <table className="dense-table" role="grid" style={{ width: '100%', tableLayout: 'fixed' }}>
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{ ...col.style, cursor: 'pointer', userSelect: 'none' }}
                  scope="col"
                  aria-sort={getAriaSortValue(col.key)}
                  tabIndex={0}
                  onKeyDown={(e: KeyboardEvent<HTMLTableCellElement>) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSort(col.key);
                    }
                  }}
                >
                  {col.label} {sortCol === col.key ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : ''}
                </th>
              ))}
            </tr>
          </thead>
        </table>

        {/* Scrollable body */}
        <div
          ref={containerRef}
          onScroll={handleScroll}
          style={{
            height: containerHeight - headerHeight - 24, /* subtract header + count bar */
            overflow: 'auto',
            position: 'relative',
          }}
        >
          {/* Spacer to maintain correct scrollbar height */}
          <div style={{ height: totalHeight, position: 'relative' }}>
            {/* Positioned visible rows */}
            <table
              className="dense-table"
              role="grid"
              style={{
                width: '100%',
                tableLayout: 'fixed',
                position: 'absolute',
                top: 0,
                left: 0,
                transform: `translateY(${offsetY}px)`,
              }}
            >
              <tbody>
                {visibleRows.map((row, i) => {
                  const globalIndex = startIndex + i;
                  return (
                    <tr
                      key={(row as Record<string, unknown>).id as string | number ?? globalIndex}
                      onClick={() => onRowClick?.(row)}
                      onKeyDown={(e: KeyboardEvent<HTMLTableRowElement>) => handleRowKeyDown(e, row)}
                      style={{
                        cursor: onRowClick ? 'pointer' : 'default',
                        height: rowHeight,
                      }}
                      tabIndex={onRowClick ? 0 : undefined}
                      role={onRowClick ? 'row' : undefined}
                    >
                      {columns.map(col => (
                        <td key={col.key} style={col.cellStyle}>
                          {col.render ? col.render(row[col.key], row) : row[col.key] as ReactNode}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

const VirtualTable = memo(VirtualTableInner) as <T extends Record<string, unknown>>(
  props: VirtualTableProps<T>
) => ReactElement;
(VirtualTable as { displayName?: string }).displayName = 'VirtualTable';
export default VirtualTable;
