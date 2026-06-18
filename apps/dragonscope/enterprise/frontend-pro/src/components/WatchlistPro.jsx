import React, { useEffect, useState, useRef, useMemo } from 'react';
import { 
  Search, 
  Plus, 
  MoreHorizontal, 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown,
  Minus,
  Trash2,
  Bell,
  TrendingUp,
  TrendingDown,
  Activity,
  LayoutGrid,
  List as ListIcon,
  Settings,
  Download,
  Filter,
  X,
  GripVertical,
  Star,
} from 'lucide-react';
import { useWatchlistStore, useTerminalStore } from '../stores/terminalStore';
import { formatPrice, formatNumber, formatPercent, getValueColor, tw } from '../utils/styles';

// Available columns configuration
const AVAILABLE_COLUMNS = [
  { id: 'symbol', label: 'Symbol', width: 80, align: 'left' },
  { id: 'last', label: 'Last', width: 90, align: 'right' },
  { id: 'change', label: 'Change', width: 80, align: 'right' },
  { id: 'changePercent', label: '% Chg', width: 80, align: 'right' },
  { id: 'open', label: 'Open', width: 90, align: 'right' },
  { id: 'high', label: 'High', width: 90, align: 'right' },
  { id: 'low', label: 'Low', width: 90, align: 'right' },
  { id: 'close', label: 'Prev Close', width: 90, align: 'right' },
  { id: 'volume', label: 'Volume', width: 100, align: 'right' },
  { id: 'avgVolume', label: 'Avg Vol', width: 100, align: 'right' },
  { id: 'marketCap', label: 'Mkt Cap', width: 100, align: 'right' },
  { id: 'pe', label: 'P/E', width: 70, align: 'right' },
  { id: 'bid', label: 'Bid', width: 90, align: 'right' },
  { id: 'ask', label: 'Ask', width: 90, align: 'right' },
  { id: 'spread', label: 'Spread', width: 70, align: 'right' },
  { id: '52wHigh', label: '52W High', width: 90, align: 'right' },
  { id: '52wLow', label: '52W Low', width: 90, align: 'right' },
  { id: 'rsi', label: 'RSI', width: 60, align: 'right' },
];

// Generate mock quote data
const generateQuote = (symbol) => {
  const basePrice = Math.random() * 500 + 10;
  const change = (Math.random() - 0.48) * basePrice * 0.05;
  const changePercent = (change / basePrice) * 100;
  
  return {
    symbol,
    last: basePrice + change,
    change,
    changePercent,
    open: basePrice * (1 + (Math.random() - 0.5) * 0.02),
    high: basePrice * (1 + Math.random() * 0.03),
    low: basePrice * (1 - Math.random() * 0.03),
    close: basePrice,
    volume: Math.floor(Math.random() * 100000000),
    avgVolume: Math.floor(Math.random() * 50000000) + 10000000,
    marketCap: Math.floor(Math.random() * 1000000000000),
    pe: Math.random() * 50 + 5,
    bid: basePrice + change - 0.01,
    ask: basePrice + change + 0.01,
    spread: 0.02,
    '52wHigh': basePrice * 1.5,
    '52wLow': basePrice * 0.6,
    rsi: Math.random() * 100,
    timestamp: Date.now(),
  };
};

// Watchlist Row Component
const WatchlistRow = ({ 
  symbol, 
  data, 
  columns, 
  isSelected, 
  onSelect, 
  onRemove, 
  onTrade,
  heatmapMode,
  index,
}) => {
  const prevData = useRef(data);
  const [flash, setFlash] = useState(null);
  
  // Flash on price change
  useEffect(() => {
    if (prevData.current && data) {
      if (data.last > prevData.current.last) {
        setFlash('up');
      } else if (data.last < prevData.current.last) {
        setFlash('down');
      }
      const timer = setTimeout(() => setFlash(null), 300);
      prevData.current = data;
      return () => clearTimeout(timer);
    }
    prevData.current = data;
  }, [data?.last]);

  if (!data) return null;

  // Calculate heatmap intensity based on % change
  const heatmapIntensity = heatmapMode 
    ? Math.min(Math.abs(data.changePercent) / 5, 1) 
    : 0;
  const heatmapColor = data.changePercent >= 0 
    ? `rgba(16, 185, 129, ${heatmapIntensity * 0.3})`
    : `rgba(239, 68, 68, ${heatmapIntensity * 0.3})`;

  const renderCell = (columnId) => {
    switch (columnId) {
      case 'symbol':
        return (
          <div className="flex items-center gap-2">
            <GripVertical className="w-3 h-3 text-slate-600 opacity-0 group-hover:opacity-100 cursor-move" />
            <span className="font-medium text-slate-200">{data.symbol}</span>
          </div>
        );
      case 'last':
        return (
          <span className={tw(
            "font-mono transition-colors",
            flash === 'up' ? "text-green-400 bg-green-400/20" : 
            flash === 'down' ? "text-red-400 bg-red-400/20" : "text-slate-200"
          )}>
            {formatPrice(data.last)}
          </span>
        );
      case 'change':
        return (
          <span className={tw("font-mono", getValueColor(data.change))}>
            {formatPrice(data.change, 2)}
          </span>
        );
      case 'changePercent':
        return (
          <div className="flex items-center justify-end gap-1">
            {data.changePercent >= 0 ? (
              <TrendingUp className="w-3 h-3 text-green-400" />
            ) : (
              <TrendingDown className="w-3 h-3 text-red-400" />
            )}
            <span className={tw("font-mono", getValueColor(data.changePercent))}>
              {formatPercent(data.changePercent)}
            </span>
          </div>
        );
      case 'volume':
        return <span className="font-mono text-slate-300">{formatNumber(data.volume, true)}</span>;
      case 'marketCap':
        return <span className="font-mono text-slate-300">{formatNumber(data.marketCap, true)}</span>;
      case 'rsi':
        const rsiColor = data.rsi > 70 ? 'text-red-400' : data.rsi < 30 ? 'text-green-400' : 'text-slate-300';
        return <span className={tw("font-mono", rsiColor)}>{data.rsi.toFixed(1)}</span>;
      case 'spread':
        return <span className="font-mono text-slate-300">{formatPrice(data.spread, 3)}</span>;
      default:
        return <span className="font-mono text-slate-300">{formatPrice(data[columnId])}</span>;
    }
  };

  return (
    <div 
      className={tw(
        "group flex items-center h-8 border-b border-slate-800/50 cursor-pointer transition-colors",
        isSelected ? "bg-blue-500/10" : "hover:bg-slate-800/30",
      )}
      style={{ backgroundColor: heatmapMode ? heatmapColor : undefined }}
      onClick={() => onSelect(data.symbol)}
    >
      {/* Cells */}
      {columns.map(col => {
        const columnDef = AVAILABLE_COLUMNS.find(c => c.id === col);
        return (
          <div 
            key={col}
            className="px-2 text-sm"
            style={{ width: columnDef?.width || 80, textAlign: columnDef?.align || 'left' }}
          >
            {renderCell(col)}
          </div>
        );
      })}

      {/* Actions */}
      <div className="flex items-center gap-1 px-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => { e.stopPropagation(); onTrade(data.symbol, 'buy'); }}
          className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded hover:bg-green-500/30"
        >
          Buy
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onTrade(data.symbol, 'sell'); }}
          className="px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30"
        >
          Sell
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(data.symbol); }}
          className="p-1 text-slate-500 hover:text-red-400"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};

// Symbol Search Modal
const SymbolSearchModal = ({ isOpen, onClose, onSelect }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const inputRef = useRef(null);

  const popularSymbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX', 'AMD', 'INTC'];

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setResults([]);
      inputRef.current?.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    if (query.length > 0) {
      // Simulate search
      const filtered = popularSymbols.filter(s => 
        s.toLowerCase().includes(query.toLowerCase())
      );
      setResults(filtered);
    } else {
      setResults([]);
    }
  }, [query]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/50" onClick={onClose}>
      <div className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-lg shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 p-4 border-b border-slate-800">
          <Search className="w-5 h-5 text-slate-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search symbol..."
            className="flex-1 bg-transparent text-slate-100 outline-none"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && results.length > 0) {
                onSelect(results[0]);
              }
            }}
          />
        </div>
        <div className="max-h-64 overflow-y-auto">
          {results.length > 0 ? (
            results.map(symbol => (
              <button
                key={symbol}
                onClick={() => onSelect(symbol)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-800 transition-colors"
              >
                <span className="font-medium text-slate-200">{symbol}</span>
                <Plus className="w-4 h-4 text-slate-500" />
              </button>
            ))
          ) : query.length > 0 ? (
            <div className="p-4 text-center text-slate-500">No results found</div>
          ) : (
            <div className="p-4">
              <span className="text-xs text-slate-500 uppercase">Popular</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {popularSymbols.map(s => (
                  <button
                    key={s}
                    onClick={() => onSelect(s)}
                    className="px-3 py-1.5 text-sm bg-slate-800 text-slate-300 rounded hover:bg-slate-700"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const WatchlistPro = () => {
  const {
    symbols,
    columns,
    sortBy,
    sortDirection,
    filter,
    heatmapMode,
    watchlistData,
    addSymbol,
    removeSymbol,
    setSortBy,
    setFilter,
    toggleHeatmapMode,
    updateWatchlistData,
  } = useWatchlistStore();

  const [showSearch, setShowSearch] = useState(false);
  const [showColumnMenu, setShowColumnMenu] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'grid'

  // Simulate real-time data updates
  useEffect(() => {
    const interval = setInterval(() => {
      symbols.forEach(symbol => {
        const existing = watchlistData[symbol];
        if (existing) {
          const change = (Math.random() - 0.5) * 0.1;
          const newLast = existing.last + change;
          updateWatchlistData(symbol, {
            ...existing,
            last: newLast,
            change: newLast - existing.close,
            changePercent: ((newLast - existing.close) / existing.close) * 100,
            timestamp: Date.now(),
          });
        } else {
          updateWatchlistData(symbol, generateQuote(symbol));
        }
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [symbols, watchlistData]);

  // Sort and filter data
  const sortedData = useMemo(() => {
    let data = symbols.map(symbol => ({
      symbol,
      ...watchlistData[symbol],
      ...generateQuote(symbol), // Fallback
    }));

    // Apply filter
    if (filter) {
      data = data.filter(d => 
        d.symbol.toLowerCase().includes(filter.toLowerCase())
      );
    }

    // Apply sort
    if (sortBy) {
      data.sort((a, b) => {
        const aVal = a[sortBy] || 0;
        const bVal = b[sortBy] || 0;
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      });
    }

    return data;
  }, [symbols, watchlistData, filter, sortBy, sortDirection]);

  const handleSort = (columnId) => {
    setSortBy(columnId);
  };

  const handleTrade = (symbol, side) => {
    console.log(`${side.toUpperCase()} order for ${symbol}`);
    // Would open order ticket
  };

  const SortIcon = ({ column }) => {
    if (sortBy !== column) return <ArrowUpDown className="w-3 h-3 text-slate-600" />;
    return sortDirection === 'asc' 
      ? <ArrowUp className="w-3 h-3 text-blue-400" />
      : <ArrowDown className="w-3 h-3 text-blue-400" />;
  };

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-slate-100">Watchlist</h3>
          <span className="text-xs text-slate-500">({symbols.length})</span>
        </div>
        
        <div className="flex items-center gap-1">
          {/* Filter Input */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter..."
              className="w-24 pl-7 pr-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* View Mode */}
          <div className="flex items-center bg-slate-800/50 rounded p-0.5">
            <button
              onClick={() => setViewMode('list')}
              className={tw(
                "p-1 rounded transition-colors",
                viewMode === 'list' ? "bg-slate-700 text-blue-400" : "text-slate-400"
              )}
            >
              <ListIcon className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={tw(
                "p-1 rounded transition-colors",
                viewMode === 'grid' ? "bg-slate-700 text-blue-400" : "text-slate-400"
              )}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>

          {/* Heatmap Toggle */}
          <button
            onClick={toggleHeatmapMode}
            className={tw(
              "p-1.5 rounded transition-colors",
              heatmapMode ? "bg-blue-500/20 text-blue-400" : "text-slate-400 hover:text-slate-200"
            )}
            title="Toggle Heatmap"
          >
            <Activity className="w-4 h-4" />
          </button>

          {/* Column Menu */}
          <div className="relative">
            <button
              onClick={() => setShowColumnMenu(!showColumnMenu)}
              className="p-1.5 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800"
            >
              <Settings className="w-4 h-4" />
            </button>
            
            {showColumnMenu && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-20">
                <div className="p-2 border-b border-slate-800">
                  <span className="text-xs font-medium text-slate-500">Columns</span>
                </div>
                {AVAILABLE_COLUMNS.map(col => (
                  <label 
                    key={col.id}
                    className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-800 cursor-pointer"
                  >
                    <input 
                      type="checkbox" 
                      checked={columns.includes(col.id)}
                      className="rounded bg-slate-800 border-slate-600"
                      readOnly
                    />
                    <span className="text-slate-300">{col.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={() => setShowSearch(true)}
            className="flex items-center gap-1 px-2 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors"
          >
            <Plus className="w-3 h-3" />
            <span className="hidden sm:inline">Add</span>
          </button>
        </div>
      </div>

      {/* Column Headers */}
      {viewMode === 'list' && (
        <div className="flex items-center h-7 px-2 border-b border-slate-800 bg-slate-800/30">
          {columns.map(col => {
            const colDef = AVAILABLE_COLUMNS.find(c => c.id === col);
            return (
              <button
                key={col}
                onClick={() => handleSort(col)}
                className="flex items-center justify-center gap-1 px-2 text-xs font-medium text-slate-400 hover:text-slate-200"
                style={{ width: colDef?.width || 80, textAlign: colDef?.align || 'left' }}
              >
                {colDef?.label}
                <SortIcon column={col} />
              </button>
            );
          })}
          <div className="w-24" /> {/* Actions column */}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {viewMode === 'list' ? (
          <div>
            {sortedData.map((data, index) => (
              <WatchlistRow
                key={data.symbol}
                symbol={data.symbol}
                data={data}
                columns={columns}
                isSelected={selectedSymbol === data.symbol}
                onSelect={setSelectedSymbol}
                onRemove={removeSymbol}
                onTrade={handleTrade}
                heatmapMode={heatmapMode}
                index={index}
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 p-2">
            {sortedData.map(data => (
              <div 
                key={data.symbol}
                onClick={() => setSelectedSymbol(data.symbol)}
                className={tw(
                  "p-3 rounded-lg border cursor-pointer transition-colors",
                  selectedSymbol === data.symbol 
                    ? "bg-blue-500/10 border-blue-500/50" 
                    : "bg-slate-800/50 border-slate-700 hover:border-slate-600"
                )}
                style={{ 
                  backgroundColor: heatmapMode 
                    ? data.changePercent >= 0 
                      ? `rgba(16, 185, 129, ${Math.min(Math.abs(data.changePercent) / 5, 1) * 0.3})`
                      : `rgba(239, 68, 68, ${Math.min(Math.abs(data.changePercent) / 5, 1) * 0.3})`
                    : undefined 
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-slate-200">{data.symbol}</span>
                  <div className="flex items-center gap-1">
                    {data.changePercent >= 0 ? (
                      <TrendingUp className="w-3 h-3 text-green-400" />
                    ) : (
                      <TrendingDown className="w-3 h-3 text-red-400" />
                    )}
                    <span className={tw("text-sm font-mono", getValueColor(data.changePercent))}>
                      {formatPercent(data.changePercent)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-lg font-mono text-slate-100">{formatPrice(data.last)}</span>
                  <span className="text-xs text-slate-500">{formatNumber(data.volume, true)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-slate-800 text-xs">
        <span className="text-slate-500">
          {sortedData.length} symbols
        </span>
        <span className="text-slate-500">
          Last update: {new Date().toLocaleTimeString()}
        </span>
      </div>

      {/* Symbol Search Modal */}
      <SymbolSearchModal
        isOpen={showSearch}
        onClose={() => setShowSearch(false)}
        onSelect={(symbol) => {
          addSymbol(symbol);
          setShowSearch(false);
        }}
      />
    </div>
  );
};

export default WatchlistPro;
