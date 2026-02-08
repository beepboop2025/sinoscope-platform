import { useState, useMemo, memo, useCallback } from 'react';

const PAGE_SIZES = [10, 25, 50, 'All'];

const DataTable = memo(({ columns, data, onRowClick }) => {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  const handleRowKeyDown = useCallback((e, row) => {
    if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onRowClick(row);
    }
  }, [onRowClick]);

  const sorted = sortCol
    ? [...data].sort((a, b) => {
        const av = a[sortCol], bv = b[sortCol];
        const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
        return sortDir === 'asc' ? cmp : -cmp;
      })
    : data;

  const getAriaSortValue = (colKey) => {
    if (sortCol !== colKey) return undefined;
    return sortDir === 'asc' ? 'ascending' : 'descending';
  };

  const showAll = pageSize === 'All';
  const totalPages = showAll ? 1 : Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);

  const paginatedRows = useMemo(() => {
    if (showAll) return sorted;
    const start = safePage * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, safePage, pageSize, showAll]);

  const handlePageSizeChange = (newSize) => {
    setPageSize(newSize);
    setPage(0);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <table className="dense-table" role="grid">
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={col.style}
                  scope="col"
                  aria-sort={getAriaSortValue(col.key)}
                  tabIndex={0}
                  onKeyDown={(e) => {
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
          <tbody>
            {paginatedRows.map((row, i) => (
              <tr
                key={row.id || i}
                onClick={() => onRowClick?.(row)}
                onKeyDown={(e) => handleRowKeyDown(e, row)}
                style={{ cursor: onRowClick ? 'pointer' : 'default' }}
                tabIndex={onRowClick ? 0 : undefined}
                role={onRowClick ? 'row' : undefined}
              >
                {columns.map(col => (
                  <td key={col.key} style={col.cellStyle}>
                    {col.render ? col.render(row[col.key], row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {sorted.length > 10 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '4px 6px', borderTop: '1px solid var(--border-1)',
          fontSize: 10, color: 'var(--text-3)', flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span>Rows:</span>
            <select
              value={pageSize}
              onChange={e => handlePageSizeChange(e.target.value === 'All' ? 'All' : Number(e.target.value))}
              style={{
                fontSize: 10, padding: '1px 4px', background: 'var(--bg-1)',
                color: 'var(--text-2)', border: '1px solid var(--border-2)',
                borderRadius: 3, cursor: 'pointer',
              }}
            >
              {PAGE_SIZES.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {!showAll && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>{safePage * pageSize + 1}–{Math.min((safePage + 1) * pageSize, sorted.length)} of {sorted.length}</span>
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={safePage === 0}
                style={{
                  background: 'none', border: '1px solid var(--border-2)', borderRadius: 3,
                  color: safePage === 0 ? 'var(--text-4)' : 'var(--text-2)',
                  cursor: safePage === 0 ? 'default' : 'pointer',
                  padding: '1px 6px', fontSize: 10,
                }}
              >
                Prev
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={safePage >= totalPages - 1}
                style={{
                  background: 'none', border: '1px solid var(--border-2)', borderRadius: 3,
                  color: safePage >= totalPages - 1 ? 'var(--text-4)' : 'var(--text-2)',
                  cursor: safePage >= totalPages - 1 ? 'default' : 'pointer',
                  padding: '1px 6px', fontSize: 10,
                }}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
DataTable.displayName = "DataTable";
export default DataTable;
