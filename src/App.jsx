import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ResponsiveGridLayout, useContainerWidth } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';

import AppShell from './components/layout/AppShell';
import CommandBar from './components/layout/CommandBar';
import { ErrorBoundary } from './components/shared/ErrorBoundary';

// Panels
import PanelForex from './components/panels/PanelForex';
import PanelStocks from './components/panels/PanelStocks';
import PanelCrypto from './components/panels/PanelCrypto';
import PanelBonds from './components/panels/PanelBonds';
import PanelCommodities from './components/panels/PanelCommodities';
import PanelEconomic from './components/panels/PanelEconomic';
import PanelNews from './components/panels/PanelNews';
import PanelChart from './components/panels/PanelChart';
import PanelCorrelation from './components/panels/PanelCorrelation';
import PanelNetwork from './components/panels/PanelNetwork';
import PanelTimeline from './components/panels/PanelTimeline';
import PanelCompany from './components/panels/PanelCompany';
import PanelAlerts from './components/panels/PanelAlerts';

// China panels
import PanelChinaMarkets from './components/panels/china/PanelChinaMarkets';
import PanelCNYTracker from './components/panels/china/PanelCNYTracker';
import PanelPBOCWatch from './components/panels/china/PanelPBOCWatch';
import PanelTradeFlow from './components/panels/china/PanelTradeFlow';
import PanelBeltRoad from './components/panels/china/PanelBeltRoad';
import PanelChinaCalendar from './components/panels/china/PanelChinaCalendar';

// Engine & hooks
import { createMarketEngine } from './engine/MarketEngine';
import { useMarketData } from './hooks/useMarketData';
import { useWebSocket } from './hooks/useWebSocket';
import { useWorkspace } from './hooks/useWorkspace';
import { useCommandBar } from './hooks/useCommandBar';
import { useCorrelation } from './hooks/useCorrelation';

// Mock data generators
import { generateMockForex } from './generators/mockForex';
import { generateMockStocks } from './generators/mockStocks';
import { generateMockCrypto } from './generators/mockCrypto';
import { generateMockEconomic, generateMockYieldCurve } from './generators/mockEconomic';

const CORRELATION_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'BTC', 'ETH', 'SOL'];

function App() {
  const engineRef = useRef(null);
  const [useMock, setUseMock] = useState(false);
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);

  // Initialize engine once
  if (!engineRef.current) {
    engineRef.current = createMarketEngine();
  }
  const engine = engineRef.current;

  // Market data from engine
  const marketData = useMarketData(engine);

  // WebSocket for real-time crypto
  useWebSocket(engine, { useMock });

  // Workspace layout
  const workspace = useWorkspace();
  const { activeWorkspace, updateLayout, activeId, addPanelToWorkspace, switchWorkspace } = workspace;

  // Correlation
  const { matrix: corrMatrix, pairs: corrPairs } = useCorrelation(marketData, CORRELATION_SYMBOLS);

  // Network data for PanelNetwork
  const networkSymbols = CORRELATION_SYMBOLS.slice(0, 6);
  const networkPairs = corrPairs || [];

  // Start engine on mount
  useEffect(() => {
    engine.start();
    return () => engine.stop();
  }, [engine]);

  // Fall back to mock data if nothing arrives after 8s
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!marketData?.forex || Object.keys(marketData.forex).length === 0) {
        setUseMock(true);
        // Seed mock data into engine manually
        const mockForex = generateMockForex();
        const mockStocks = generateMockStocks();
        const mockCrypto = generateMockCrypto();
        const mockBonds = generateMockYieldCurve();
        const mockEcon = generateMockEconomic();

        for (const [k, v] of Object.entries(mockForex)) engine.updateFromWS({ symbol: k, ...v });
        for (const [k, v] of Object.entries(mockStocks)) engine.updateFromWS({ symbol: k, ...v });
        for (const [k, v] of Object.entries(mockCrypto)) engine.updateFromWS({ symbol: k + 'USDT', ...v });
      }
    }, 8000);
    return () => clearTimeout(timer);
  }, [engine, marketData]);

  // Generate events from market data
  const prevMarketRef = useRef({});
  useEffect(() => {
    if (!marketData) return;
    const newEvents = [];
    const prev = prevMarketRef.current;

    // Check stocks for significant moves
    const stocks = marketData.stocks || {};
    for (const [sym, data] of Object.entries(stocks)) {
      if (!data?.changePct) continue;
      const pct = Math.abs(Number(data.changePct) || 0);
      if (pct >= 2) {
        const key = `stock_${sym}_${new Date().toDateString()}`;
        if (!prev[key]) {
          prev[key] = true;
          newEvents.push({
            id: key,
            type: 'price_alert',
            symbol: sym,
            message: `${sym} ${data.changePct > 0 ? 'surged' : 'dropped'} ${pct.toFixed(1)}% to $${(Number(data.price) || 0).toFixed(2)}`,
            timestamp: Date.now(),
          });
        }
      }
    }

    // Check crypto for significant moves
    const crypto = marketData.crypto || {};
    for (const [sym, data] of Object.entries(crypto)) {
      if (!data?.changePct) continue;
      const pct = Math.abs(Number(data.changePct) || 0);
      if (pct >= 3) {
        const key = `crypto_${sym}_${new Date().toDateString()}`;
        if (!prev[key]) {
          prev[key] = true;
          newEvents.push({
            id: key,
            type: 'price_alert',
            symbol: sym,
            message: `${sym} ${data.changePct > 0 ? 'rallied' : 'fell'} ${pct.toFixed(1)}% to $${(Number(data.price) || 0).toFixed(2)}`,
            timestamp: Date.now(),
          });
        }
      }
    }

    // Generate initial events on first data load
    if (Object.keys(prev).length === 0) {
      // Add some baseline market events
      const starters = [];
      if (Object.keys(stocks).length > 0) {
        starters.push({
          id: 'init_stocks',
          type: 'economic',
          message: `Market data loaded: tracking ${Object.keys(stocks).length} stocks`,
          timestamp: Date.now() - 2000,
        });
      }
      if (Object.keys(crypto).length > 0) {
        const btc = crypto.BTC || crypto.BTCUSDT;
        if (btc?.price) {
          starters.push({
            id: 'init_btc',
            type: 'price_alert',
            symbol: 'BTC',
            message: `Bitcoin trading at $${(Number(btc.price) || 0).toLocaleString()}`,
            timestamp: Date.now() - 1000,
          });
        }
      }
      if (marketData.forex && Object.keys(marketData.forex).length > 0) {
        starters.push({
          id: 'init_forex',
          type: 'economic',
          message: `Forex feed active: ${Object.keys(marketData.forex).length} currency pairs`,
          timestamp: Date.now() - 3000,
        });
      }
      if (marketData.bonds) {
        starters.push({
          id: 'init_bonds',
          type: 'economic',
          message: 'Treasury yield data connected via FRED API',
          timestamp: Date.now() - 4000,
        });
      }
      newEvents.push(...starters);
      prev._initialized = true;
    }

    if (newEvents.length > 0) {
      setEvents(prev2 => [...newEvents, ...prev2].slice(0, 50));
    }
    prevMarketRef.current = prev;
  }, [marketData]);

  // Command bar
  const handleCommand = useCallback((cmd) => {
    if (cmd.action === 'workspace') {
      switchWorkspace(cmd.target);
    } else if (cmd.action === 'addPanel') {
      addPanelToWorkspace(cmd.target);
    }
  }, [switchWorkspace, addPanelToWorkspace]);

  const commandBar = useCommandBar({ onCommand: handleCommand });

  // Layout change
  const handleLayoutChange = useCallback((layout) => {
    updateLayout(activeId, layout);
  }, [updateLayout, activeId]);

  // Render a panel by its id
  const renderPanel = useCallback((panelId) => {
    switch (panelId) {
      case 'forex':
        return <PanelForex data={marketData?.forex} />;
      case 'stocks':
        return <PanelStocks data={marketData?.stocks} />;
      case 'crypto':
        return <PanelCrypto data={marketData?.crypto} />;
      case 'bonds':
        return <PanelBonds data={marketData?.bonds} />;
      case 'commodities':
        return <PanelCommodities data={marketData?.commodities} />;
      case 'economic':
        return <PanelEconomic data={marketData?.economic} />;
      case 'news':
        return <PanelNews />;
      case 'chart':
        return <PanelChart symbol="BTC" data={[]} />;
      case 'correlation':
        return <PanelCorrelation matrix={corrMatrix} symbols={CORRELATION_SYMBOLS} />;
      case 'network':
        return <PanelNetwork pairs={networkPairs} symbols={networkSymbols} />;
      case 'timeline':
        return <PanelTimeline events={events} />;
      case 'company':
        return <PanelCompany symbol="AAPL" />;
      case 'alerts':
        return <PanelAlerts alerts={alerts} />;
      case 'chinaMarkets':
        return <PanelChinaMarkets />;
      case 'cnyTracker':
        return <PanelCNYTracker />;
      case 'pbocWatch':
        return <PanelPBOCWatch />;
      case 'tradeFlow':
        return <PanelTradeFlow />;
      case 'beltRoad':
        return <PanelBeltRoad />;
      case 'chinaCalendar':
        return <PanelChinaCalendar />;
      default:
        return <div style={{ padding: 16, color: 'var(--text-3)', fontSize: 12 }}>Unknown panel: {panelId}</div>;
    }
  }, [marketData, corrMatrix, corrPairs, networkPairs, networkSymbols, events, alerts]);

  const layout = activeWorkspace?.layout || [];
  const panels = activeWorkspace?.panels || [];

  const { containerRef: gridRef, width: containerWidth, mounted: gridMounted } = useContainerWidth();

  return (
    <AppShell
      marketData={marketData}
      wsStatus={useMock ? 'mock' : 'live'}
      workspace={workspace}
      onOpenCommandBar={() => commandBar.setIsOpen(true)}
    >
      <div ref={gridRef}>
        {gridMounted && containerWidth > 0 && (
          <ResponsiveGridLayout
            className="layout"
            width={containerWidth}
            layouts={{ lg: layout }}
            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480 }}
            cols={{ lg: 12, md: 10, sm: 6, xs: 4 }}
            rowHeight={60}
            isDraggable
            isResizable
            compactType="vertical"
            onLayoutChange={handleLayoutChange}
            draggableHandle=".panel-titlebar"
            margin={[8, 8]}
          >
            {panels.map((panelId) => (
              <div key={panelId}>
                <ErrorBoundary>
                  {renderPanel(panelId)}
                </ErrorBoundary>
              </div>
            ))}
          </ResponsiveGridLayout>
        )}
      </div>

      <CommandBar
        isOpen={commandBar.isOpen}
        query={commandBar.query}
        setQuery={commandBar.setQuery}
        filtered={commandBar.filtered}
        activeIndex={commandBar.activeIndex}
        setActiveIndex={commandBar.setActiveIndex}
        execute={commandBar.execute}
        handleKeyDown={commandBar.handleKeyDown}
        onClose={() => commandBar.setIsOpen(false)}
      />
    </AppShell>
  );
}

export default App;
