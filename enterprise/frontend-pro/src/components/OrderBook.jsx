import React, { useEffect, useState, useRef, useMemo } from 'react';
import { 
  ArrowUp, 
  ArrowDown, 
  Activity, 
  Settings, 
  Filter,
  Pause,
  Play,
  Download,
  Maximize2,
  LayoutGrid,
  BarChart3,
} from 'lucide-react';
import { useOrderBookStore, useTerminalStore } from '../stores/terminalStore';
import { formatPrice, formatNumber, tw } from '../utils/styles';

// Generate mock L2 order book data
const generateOrderBookData = (symbol, basePrice = 150) => {
  const bids = [];
  const asks = [];
  const levels = 20;
  
  // Generate bids (buy orders below current price)
  for (let i = 0; i < levels; i++) {
    const price = basePrice - (i * 0.01) - (Math.random() * 0.05);
    const size = Math.floor(Math.random() * 5000) + 100;
    const orders = Math.floor(Math.random() * 50) + 1;
    bids.push({
      price: parseFloat(price.toFixed(2)),
      size,
      orders,
      total: 0, // Will be calculated
    });
  }
  
  // Generate asks (sell orders above current price)
  for (let i = 0; i < levels; i++) {
    const price = basePrice + (i * 0.01) + (Math.random() * 0.05);
    const size = Math.floor(Math.random() * 5000) + 100;
    const orders = Math.floor(Math.random() * 50) + 1;
    asks.push({
      price: parseFloat(price.toFixed(2)),
      size,
      orders,
      total: 0, // Will be calculated
    });
  }
  
  // Calculate cumulative totals
  let bidTotal = 0;
  bids.forEach(bid => {
    bidTotal += bid.size;
    bid.total = bidTotal;
  });
  
  let askTotal = 0;
  asks.forEach(ask => {
    askTotal += ask.size;
    ask.total = askTotal;
  });
  
  return { bids, asks, sequence: Date.now() };
};

// Generate mock trades
const generateTrade = (basePrice = 150) => {
  const isBuy = Math.random() > 0.45; // Slight buy bias
  const priceOffset = (Math.random() - 0.5) * 0.5;
  const price = parseFloat((basePrice + priceOffset).toFixed(2));
  const size = Math.floor(Math.random() * 1000) + 1;
  
  return {
    price,
    size,
    side: isBuy ? 'buy' : 'sell',
    time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    exchange: ['NYSE', 'NASDAQ', 'BATS', 'IEX'][Math.floor(Math.random() * 4)],
  };
};

// Order Book Row Component
const OrderBookRow = ({ price, size, total, maxTotal, side, isSpread = false, highlight = false }) => {
  const percentage = (total / maxTotal) * 100;
  const barColor = side === 'bid' 
    ? 'bg-green-500/20' 
    : side === 'ask' 
      ? 'bg-red-500/20' 
      : 'bg-slate-500/20';
  
  return (
    <div className={tw(
      "relative flex items-center h-6 text-xs font-mono cursor-pointer hover:bg-slate-800/50 transition-colors",
      highlight && "bg-yellow-500/10"
    )}>
      {/* Size Bar */}
      <div 
        className={tw("absolute top-0 h-full transition-all duration-300", barColor)}
        style={{ 
          [side === 'bid' ? 'right' : 'left']: 0,
          width: `${percentage}%`,
        }}
      />
      
      {/* Content */}
      <div className="relative z-10 flex-1 flex items-center px-2">
        {side === 'ask' && (
          <>
            <span className="w-16 text-right text-slate-400">{formatNumber(size, true)}</span>
            <span className="w-16 text-right text-slate-500">{total.toLocaleString()}</span>
            <span className={tw(
              "flex-1 text-right",
              isSpread ? "text-slate-300" : "text-red-400"
            )}>
              {formatPrice(price)}
            </span>
          </>
        )}
        {side === 'bid' && (
          <>
            <span className={tw(
              "w-20 text-left",
              isSpread ? "text-slate-300" : "text-green-400"
            )}>
              {formatPrice(price)}
            </span>
            <span className="w-16 text-left text-slate-500">{total.toLocaleString()}</span>
            <span className="w-16 text-left text-slate-400">{formatNumber(size, true)}</span>
          </>
        )}
      </div>
    </div>
  );
};

// Trade Tape Row Component
const TradeRow = ({ trade, prevTrade }) => {
  const isUp = prevTrade ? trade.price > prevTrade.price : trade.side === 'buy';
  const isSame = prevTrade ? trade.price === prevTrade.price : false;
  
  return (
    <div className="flex items-center h-5 px-2 text-xs font-mono hover:bg-slate-800/30 transition-colors">
      <span className="w-16 text-slate-500">{trade.time}</span>
      <span className={tw(
        "w-16 text-right",
        trade.side === 'buy' ? "text-green-400" : "text-red-400"
      )}>
        {formatPrice(trade.price)}
      </span>
      <span className="w-16 text-right text-slate-300">{trade.size}</span>
      <span className="flex-1 text-right text-slate-500 text-xs">{trade.exchange}</span>
      <span className={tw(
        "ml-2",
        isUp ? "text-green-400" : isSame ? "text-slate-400" : "text-red-400"
      )}>
        {isUp ? <ArrowUp className="w-3 h-3" /> : isSame ? null : <ArrowDown className="w-3 h-3" />}
      </span>
    </div>
  );
};

// Market Depth Visualization (Heatmap)
const MarketDepthHeatmap = ({ orderBook }) => {
  const maxTotal = Math.max(
    ...orderBook.bids.map(b => b.total),
    ...orderBook.asks.map(a => a.total)
  );
  
  // Create price buckets for heatmap
  const bucketSize = 0.1;
  const buckets = new Map();
  
  [...orderBook.bids, ...orderBook.asks].forEach(level => {
    const bucketPrice = Math.floor(level.price / bucketSize) * bucketSize;
    const existing = buckets.get(bucketPrice) || { bid: 0, ask: 0 };
    if (orderBook.bids.find(b => b.price === level.price)) {
      existing.bid += level.size;
    } else {
      existing.ask += level.size;
    }
    buckets.set(bucketPrice, existing);
  });
  
  const sortedBuckets = Array.from(buckets.entries())
    .sort((a, b) => b[0] - a[0])
    .slice(0, 20);
  
  const maxSize = Math.max(...sortedBuckets.map(([, v]) => Math.max(v.bid, v.ask)));
  
  return (
    <div className="h-full overflow-y-auto">
      {sortedBuckets.map(([price, data]) => {
        const bidIntensity = (data.bid / maxSize) * 100;
        const askIntensity = (data.ask / maxSize) * 100;
        
        return (
          <div key={price} className="flex items-center h-5 text-xs">
            <div className="flex-1 flex justify-end pr-1">
              {data.bid > 0 && (
                <div 
                  className="h-full bg-green-500/30 rounded-sm"
                  style={{ width: `${bidIntensity}%` }}
                />
              )}
            </div>
            <span className="w-16 text-center text-slate-300 font-mono">
              {formatPrice(price)}
            </span>
            <div className="flex-1 flex justify-start pl-1">
              {data.ask > 0 && (
                <div 
                  className="h-full bg-red-500/30 rounded-sm"
                  style={{ width: `${askIntensity}%` }}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const OrderBook = ({ symbol = 'AAPL' }) => {
  const [orderBook, setOrderBook] = useState({ bids: [], asks: [], sequence: 0 });
  const [trades, setTrades] = useState([]);
  const [isPaused, setIsPaused] = useState(false);
  const [viewMode, setViewMode] = useState('split'); // 'split', 'bid', 'ask', 'heatmap'
  const [aggregation, setAggregation] = useState(0.01);
  const [showSettings, setShowSettings] = useState(false);
  const [spread, setSpread] = useState({ bid: 0, ask: 0 });
  const [lastPrice, setLastPrice] = useState(0);
  
  const scrollRef = useRef(null);
  const maxBidTotal = orderBook.bids[0]?.total || 1;
  const maxAskTotal = orderBook.asks[0]?.total || 1;
  const maxTotal = Math.max(maxBidTotal, maxAskTotal);

  // Simulate real-time updates
  useEffect(() => {
    if (isPaused) return;
    
    // Initial data
    setOrderBook(generateOrderBookData(symbol));
    
    const interval = setInterval(() => {
      // Update order book
      setOrderBook(prev => {
        const newData = generateOrderBookData(symbol, lastPrice || 150);
        return newData;
      });
      
      // Add new trade
      const newTrade = generateTrade(lastPrice || 150);
      setTrades(prev => {
        const updated = [newTrade, ...prev].slice(0, 100);
        return updated;
      });
      
      setLastPrice(newTrade.price);
    }, 100);
    
    return () => clearInterval(interval);
  }, [symbol, isPaused, lastPrice]);

  // Calculate spread
  useEffect(() => {
    if (orderBook.bids.length > 0 && orderBook.asks.length > 0) {
      setSpread({
        bid: orderBook.bids[0].price,
        ask: orderBook.asks[0].price,
      });
    }
  }, [orderBook]);

  // Auto-scroll trades
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [trades]);

  const spreadAmount = spread.ask - spread.bid;
  const spreadPercent = spread.bid > 0 ? (spreadAmount / spread.bid) * 100 : 0;

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-slate-100">{symbol}</h3>
          <div className="flex items-center gap-1 text-xs">
            <span className="text-slate-400">Spread:</span>
            <span className="text-slate-200 font-mono">{formatPrice(spreadAmount)}</span>
            <span className="text-slate-500">({spreadPercent.toFixed(3)}%)</span>
          </div>
        </div>
        
        <div className="flex items-center gap-1">
          {/* View Mode Toggle */}
          <div className="flex items-center bg-slate-800/50 rounded p-0.5">
            <button
              onClick={() => setViewMode('split')}
              className={tw(
                "p-1 rounded transition-colors",
                viewMode === 'split' ? "bg-slate-700 text-blue-400" : "text-slate-400 hover:text-slate-200"
              )}
              title="Split View"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('heatmap')}
              className={tw(
                "p-1 rounded transition-colors",
                viewMode === 'heatmap' ? "bg-slate-700 text-blue-400" : "text-slate-400 hover:text-slate-200"
              )}
              title="Heatmap"
            >
              <BarChart3 className="w-4 h-4" />
            </button>
          </div>

          {/* Play/Pause */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={tw(
              "p-1.5 rounded transition-colors",
              isPaused ? "text-yellow-400 bg-yellow-400/10" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            )}
          >
            {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          </button>

          <button className="p-1.5 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800">
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 min-h-0 flex">
        {viewMode === 'heatmap' ? (
          <div className="flex-1 p-2">
            <div className="text-xs text-slate-500 mb-2 text-center">Market Depth Heatmap</div>
            <MarketDepthHeatmap orderBook={orderBook} />
          </div>
        ) : (
          <>
            {/* Order Book */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Column Headers */}
              <div className="flex items-center h-6 px-2 text-xs font-medium text-slate-500 border-b border-slate-800">
                {viewMode !== 'ask' && (
                  <>
                    <span className="w-16 text-right">Bid Size</span>
                    <span className="w-16 text-right">Total</span>
                    <span className="flex-1 text-right">Price</span>
                  </>
                )}
                {viewMode === 'split' && <span className="w-px h-4 bg-slate-700 mx-2" />}
                {viewMode !== 'bid' && (
                  <>
                    <span className="flex-1 text-left">Price</span>
                    <span className="w-16 text-left">Total</span>
                    <span className="w-16 text-left">Ask Size</span>
                  </>
                )}
              </div>

              {/* Asks (Reversed) */}
              {(viewMode === 'split' || viewMode === 'ask') && (
                <div className="flex-1 overflow-y-auto flex flex-col-reverse">
                  {orderBook.asks.slice().reverse().map((ask, i) => (
                    <OrderBookRow
                      key={`ask-${ask.price}-${i}`}
                      price={ask.price}
                      size={ask.size}
                      total={ask.total}
                      maxTotal={maxTotal}
                      side="ask"
                    />
                  ))}
                </div>
              )}

              {/* Spread */}
              <div className="flex items-center justify-center h-8 bg-slate-800/50 border-y border-slate-700">
                <span className="text-sm font-mono text-slate-300">
                  {formatPrice(spread.bid)} ← Spread → {formatPrice(spread.ask)}
                </span>
              </div>

              {/* Bids */}
              {(viewMode === 'split' || viewMode === 'bid') && (
                <div className="flex-1 overflow-y-auto">
                  {orderBook.bids.map((bid, i) => (
                    <OrderBookRow
                      key={`bid-${bid.price}-${i}`}
                      price={bid.price}
                      size={bid.size}
                      total={bid.total}
                      maxTotal={maxTotal}
                      side="bid"
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Trade Tape */}
            <div className="w-48 border-l border-slate-800 flex flex-col bg-slate-900/30">
              <div className="flex items-center justify-between px-2 py-1.5 border-b border-slate-800">
                <span className="text-xs font-medium text-slate-400">Time & Sales</span>
                <Activity className="w-3 h-3 text-slate-500" />
              </div>
              <div 
                ref={scrollRef}
                className="flex-1 overflow-y-auto"
              >
                {trades.slice(0, 50).map((trade, i) => (
                  <TradeRow 
                    key={i} 
                    trade={trade} 
                    prevTrade={trades[i + 1]}
                  />
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer Stats */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-slate-800 text-xs">
        <div className="flex items-center gap-4">
          <span className="text-slate-500">
            Bid Vol: <span className="text-green-400">{formatNumber(orderBook.bids.reduce((a, b) => a + b.size, 0))}</span>
          </span>
          <span className="text-slate-500">
            Ask Vol: <span className="text-red-400">{formatNumber(orderBook.asks.reduce((a, b) => a + b.size, 0))}</span>
          </span>
        </div>
        <span className="text-slate-500">
          Seq: {orderBook.sequence}
        </span>
      </div>
    </div>
  );
};

export default OrderBook;
