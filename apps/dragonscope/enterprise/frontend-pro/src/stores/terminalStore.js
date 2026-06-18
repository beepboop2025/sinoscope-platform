import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

export const useTerminalStore = create(
  immer(
    persist(
      (set, get) => ({
        // Layout State
        sidebarCollapsed: false,
        panels: [
          { id: 'main-chart', type: 'chart', title: 'Chart', symbol: 'AAPL', timeframe: '1D', detached: false },
          { id: 'order-book', type: 'orderbook', title: 'Order Book', symbol: 'AAPL', detached: false },
          { id: 'watchlist', type: 'watchlist', title: 'Watchlist', detached: false },
          { id: 'news', type: 'news', title: 'News Feed', detached: false },
        ],
        activePanel: 'main-chart',
        detachedWindows: [],
        
        // Command Palette
        commandPaletteOpen: false,
        
        // Global Settings
        theme: 'dark',
        chartDefaults: {
          type: 'candlestick',
          indicators: ['volume', 'sma20'],
          timeframe: '1D',
        },
        
        // Real-time Data
        connections: {
          marketData: false,
          news: false,
          orderbook: false,
        },
        lastPrices: {},
        
        // Actions
        toggleSidebar: () => set((state) => { state.sidebarCollapsed = !state.sidebarCollapsed; }),
        
        setActivePanel: (id) => set((state) => { state.activePanel = id; }),
        
        updatePanel: (id, updates) => set((state) => {
          const panel = state.panels.find(p => p.id === id);
          if (panel) Object.assign(panel, updates);
        }),
        
        addPanel: (panel) => set((state) => {
          state.panels.push({ ...panel, id: `panel-${Date.now()}`, detached: false });
        }),
        
        removePanel: (id) => set((state) => {
          state.panels = state.panels.filter(p => p.id !== id);
        }),
        
        detachPanel: (id) => set((state) => {
          const panel = state.panels.find(p => p.id === id);
          if (panel) {
            panel.detached = true;
            state.detachedWindows.push(panel);
          }
        }),
        
        attachPanel: (id) => set((state) => {
          const panel = state.detachedWindows.find(p => p.id === id);
          if (panel) {
            panel.detached = false;
            state.detachedWindows = state.detachedWindows.filter(p => p.id !== id);
          }
        }),
        
        toggleCommandPalette: () => set((state) => { 
          state.commandPaletteOpen = !state.commandPaletteOpen; 
        }),
        
        setCommandPaletteOpen: (open) => set((state) => { 
          state.commandPaletteOpen = open; 
        }),
        
        updateLastPrice: (symbol, price) => set((state) => {
          state.lastPrices[symbol] = {
            price,
            timestamp: Date.now(),
            prevPrice: state.lastPrices[symbol]?.price || price,
          };
        }),
        
        setConnectionStatus: (service, connected) => set((state) => {
          state.connections[service] = connected;
        }),
        
        reorderPanels: (newOrder) => set((state) => {
          state.panels = newOrder.map(id => state.panels.find(p => p.id === id)).filter(Boolean);
        }),
      }),
      {
        name: 'dragonscope-terminal',
        partialize: (state) => ({
          sidebarCollapsed: state.sidebarCollapsed,
          panels: state.panels.map(p => ({ ...p, detached: false })),
          theme: state.theme,
          chartDefaults: state.chartDefaults,
        }),
      }
    )
  )
);

// Watchlist Store
export const useWatchlistStore = create(
  immer((set, get) => ({
    symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX'],
    columns: ['symbol', 'last', 'change', 'changePercent', 'volume', 'bid', 'ask', 'spread'],
    sortBy: 'symbol',
    sortDirection: 'asc',
    filter: '',
    heatmapMode: false,
    
    watchlistData: {},
    
    addSymbol: (symbol) => set((state) => {
      if (!state.symbols.includes(symbol.toUpperCase())) {
        state.symbols.push(symbol.toUpperCase());
      }
    }),
    
    removeSymbol: (symbol) => set((state) => {
      state.symbols = state.symbols.filter(s => s !== symbol);
    }),
    
    reorderSymbols: (newOrder) => set((state) => {
      state.symbols = newOrder;
    }),
    
    updateWatchlistData: (symbol, data) => set((state) => {
      state.watchlistData[symbol] = { ...state.watchlistData[symbol], ...data, lastUpdate: Date.now() };
    }),
    
    setSortBy: (column) => set((state) => {
      if (state.sortBy === column) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortBy = column;
        state.sortDirection = 'asc';
      }
    }),
    
    setFilter: (filter) => set((state) => { state.filter = filter; }),
    toggleHeatmapMode: () => set((state) => { state.heatmapMode = !state.heatmapMode; }),
  }))
);

// Chart Store
export const useChartStore = create(
  immer((set, get) => ({
    charts: {},
    
    getChartConfig: (chartId) => get().charts[chartId] || {
      symbol: 'AAPL',
      timeframe: '1D',
      type: 'candlestick',
      indicators: ['volume'],
      compareSymbols: [],
      drawings: [],
    },
    
    updateChartConfig: (chartId, updates) => set((state) => {
      if (!state.charts[chartId]) state.charts[chartId] = {};
      Object.assign(state.charts[chartId], updates);
    }),
    
    addIndicator: (chartId, indicator) => set((state) => {
      if (!state.charts[chartId]) state.charts[chartId] = { indicators: [] };
      if (!state.charts[chartId].indicators.includes(indicator)) {
        state.charts[chartId].indicators.push(indicator);
      }
    }),
    
    removeIndicator: (chartId, indicator) => set((state) => {
      if (state.charts[chartId]) {
        state.charts[chartId].indicators = state.charts[chartId].indicators.filter(i => i !== indicator);
      }
    }),
    
    addComparison: (chartId, symbol) => set((state) => {
      if (!state.charts[chartId]) state.charts[chartId] = { compareSymbols: [] };
      if (!state.charts[chartId].compareSymbols.includes(symbol)) {
        state.charts[chartId].compareSymbols.push(symbol);
      }
    }),
    
    removeComparison: (chartId, symbol) => set((state) => {
      if (state.charts[chartId]) {
        state.charts[chartId].compareSymbols = state.charts[chartId].compareSymbols.filter(s => s !== symbol);
      }
    }),
    
    addDrawing: (chartId, drawing) => set((state) => {
      if (!state.charts[chartId]) state.charts[chartId] = { drawings: [] };
      state.charts[chartId].drawings.push({ ...drawing, id: `draw-${Date.now()}` });
    }),
    
    removeDrawing: (chartId, drawingId) => set((state) => {
      if (state.charts[chartId]) {
        state.charts[chartId].drawings = state.charts[chartId].drawings.filter(d => d.id !== drawingId);
      }
    }),
  }))
);

// Order Book Store
export const useOrderBookStore = create(
  immer((set, get) => ({
    orderbooks: {},
    trades: {},
    
    getOrderBook: (symbol) => get().orderbooks[symbol] || { bids: [], asks: [], lastUpdate: 0 },
    getTrades: (symbol) => get().trades[symbol] || [],
    
    updateOrderBook: (symbol, data) => set((state) => {
      state.orderbooks[symbol] = {
        bids: data.bids || [],
        asks: data.asks || [],
        lastUpdate: Date.now(),
        sequence: data.sequence,
      };
    }),
    
    addTrade: (symbol, trade) => set((state) => {
      if (!state.trades[symbol]) state.trades[symbol] = [];
      state.trades[symbol].unshift({ ...trade, id: `trade-${Date.now()}-${Math.random()}` });
      if (state.trades[symbol].length > 1000) {
        state.trades[symbol] = state.trades[symbol].slice(0, 1000);
      }
    }),
    
    clearTrades: (symbol) => set((state) => {
      state.trades[symbol] = [];
    }),
  }))
);

// News Store
export const useNewsStore = create(
  immer((set, get) => ({
    articles: [],
    filters: {
      symbols: [],
      sectors: [],
      sources: [],
      sentiment: null,
    },
    highlightedKeywords: [],
    
    addArticle: (article) => set((state) => {
      state.articles.unshift({ ...article, id: `news-${Date.now()}-${Math.random()}` });
      if (state.articles.length > 500) {
        state.articles = state.articles.slice(0, 500);
      }
    }),
    
    setFilters: (filters) => set((state) => {
      state.filters = { ...state.filters, ...filters };
    }),
    
    addHighlightedKeyword: (keyword) => set((state) => {
      if (!state.highlightedKeywords.includes(keyword)) {
        state.highlightedKeywords.push(keyword);
      }
    }),
    
    removeHighlightedKeyword: (keyword) => set((state) => {
      state.highlightedKeywords = state.highlightedKeywords.filter(k => k !== keyword);
    }),
    
    getFilteredArticles: () => {
      const { articles, filters } = get();
      return articles.filter(article => {
        if (filters.symbols.length > 0 && !filters.symbols.some(s => article.symbols?.includes(s))) return false;
        if (filters.sectors.length > 0 && !filters.sectors.includes(article.sector)) return false;
        if (filters.sources.length > 0 && !filters.sources.includes(article.source)) return false;
        if (filters.sentiment && article.sentiment !== filters.sentiment) return false;
        return true;
      });
    },
  }))
);
