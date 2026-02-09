import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ResponsiveGridLayout, useContainerWidth } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';

import AppShell from './components/layout/AppShell';
import CommandBar from './components/layout/CommandBar';
import ShortcutsModal from './components/shared/ShortcutsModal';
import { ErrorBoundary } from './components/shared/ErrorBoundary';
import OfflineIndicator from './components/shared/OfflineIndicator';

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
import PanelSqlQuery from './components/panels/PanelSqlQuery';
import PanelGithubTrending from './components/panels/PanelGithubTrending';
import PanelHuggingFace from './components/panels/PanelHuggingFace';
import PanelSentiment from './components/panels/PanelSentiment';
import PanelSectors from './components/panels/PanelSectors';
import PanelWatchlist from './components/panels/PanelWatchlist';
import PanelDefi from './components/panels/PanelDefi';
import PanelCryptoGlobal from './components/panels/PanelCryptoGlobal';
import PanelRedditSentiment from './components/panels/PanelRedditSentiment';
import PanelSECFilings from './components/panels/PanelSECFilings';
import PanelResearchPapers from './components/panels/PanelResearchPapers';
import PanelML from './components/panels/PanelML';
import PanelSignals from './components/panels/PanelSignals';
import PanelCandlestick from './components/panels/PanelCandlestick';
import PanelPortfolio from './components/panels/PanelPortfolio';
import PanelEarningsCalendar from './components/panels/PanelEarningsCalendar';

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
import { useMLEngine } from './hooks/useMLEngine';
import { useDataStatus } from './hooks/useDataStatus';
import { usePatternEngine } from './hooks/usePatternEngine';
import { useTechnicals } from './hooks/useTechnicals';
import { createTimelineEngine } from './engine/TimelineEngine';

// Mock data generators
import { generateMockForex } from './generators/mockForex';
import { generateMockStocks } from './generators/mockStocks';
import { generateMockCrypto } from './generators/mockCrypto';
import { generateMockEconomic, generateMockYieldCurve } from './generators/mockEconomic';

const CORRELATION_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'BTC', 'ETH', 'SOL'];

function App() {
  // Remove splash screen once React has mounted
  useEffect(() => {
    const splash = document.getElementById('splash');
    if (splash) {
      requestAnimationFrame(() => {
        splash.classList.add('splash-fade-out');
        setTimeout(() => splash.remove(), 600);
      });
    }
  }, []);

  const engineRef = useRef(null);
  const [useMock, setUseMock] = useState(false);
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [corrWindow, setCorrWindow] = useState(30);

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
  const { matrix: corrMatrix, pairs: corrPairs } = useCorrelation(marketData, CORRELATION_SYMBOLS, corrWindow);

  // ML Engine
  const mlEngine = useMLEngine(marketData);

  // Data status notifications
  useDataStatus(marketData, useMock ? 'mock' : 'live');

  // Pattern detection engine
  const patternEngine = usePatternEngine(marketData);

  // Technical indicators engine
  const technicals = useTechnicals(marketData);

  // Timeline engine
  const timelineRef = useRef(null);
  if (!timelineRef.current) {
    timelineRef.current = createTimelineEngine();
  }

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

  // Generate events from market data using TimelineEngine
  const prevMarketRef = useRef({});
  useEffect(() => {
    if (!marketData) return;
    const timeline = timelineRef.current;
    const prev = prevMarketRef.current;
    let added = false;

    // Check stocks for significant moves
    const stocks = marketData.stocks || {};
    for (const [sym, data] of Object.entries(stocks)) {
      if (!data?.changePct) continue;
      const pct = Math.abs(Number(data.changePct) || 0);
      if (pct >= 2) {
        const key = `stock_${sym}_${new Date().toDateString()}`;
        if (!prev[key]) {
          prev[key] = true;
          timeline.addEvent({
            id: key,
            type: 'earnings',
            title: `${sym} ${data.changePct > 0 ? 'surged' : 'dropped'} ${pct.toFixed(1)}%`,
            timestamp: Date.now(),
            symbols: [sym],
            impact: pct >= 5 ? 'high' : 'medium',
            source: 'market_data',
          });
          timeline.capturePriceAtEvent(sym, Date.now(), Number(data.price) || 0);
          added = true;
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
          const cleanSym = sym.replace('USDT', '');
          timeline.addEvent({
            id: key,
            type: 'economic',
            title: `${cleanSym} ${data.changePct > 0 ? 'rallied' : 'fell'} ${pct.toFixed(1)}%`,
            timestamp: Date.now(),
            symbols: [cleanSym],
            impact: pct >= 10 ? 'high' : 'medium',
            source: 'market_data',
          });
          timeline.capturePriceAtEvent(cleanSym, Date.now(), Number(data.price) || 0);
          added = true;
        }
      }
    }

    // Generate initial events on first data load
    if (Object.keys(prev).length === 0) {
      if (Object.keys(stocks).length > 0) {
        timeline.addEvent({
          id: 'init_stocks', type: 'economic',
          title: `Market data loaded: tracking ${Object.keys(stocks).length} stocks`,
          timestamp: Date.now() - 2000, symbols: [], impact: 'low', source: 'system',
        });
        added = true;
      }
      if (Object.keys(crypto).length > 0) {
        const btc = crypto.BTC || crypto.BTCUSDT;
        if (btc?.price) {
          timeline.addEvent({
            id: 'init_btc', type: 'economic',
            title: `Bitcoin trading at $${(Number(btc.price) || 0).toLocaleString()}`,
            timestamp: Date.now() - 1000, symbols: ['BTC'], impact: 'low', source: 'system',
          });
          added = true;
        }
      }
      if (marketData.forex && Object.keys(marketData.forex).length > 0) {
        timeline.addEvent({
          id: 'init_forex', type: 'economic',
          title: `Forex feed active: ${Object.keys(marketData.forex).length} currency pairs`,
          timestamp: Date.now() - 3000, symbols: [], impact: 'low', source: 'system',
        });
        added = true;
      }
      if (marketData.bonds) {
        timeline.addEvent({
          id: 'init_bonds', type: 'economic',
          title: 'Treasury yield data connected via FRED API',
          timestamp: Date.now() - 4000, symbols: [], impact: 'low', source: 'system',
        });
        added = true;
      }
      prev._initialized = true;
    }

    // Build timeline and convert to event format for PanelTimeline
    if (added) {
      const regime = timeline.getMarketRegime(24);
      const timelineEvents = timeline.createTimeline(
        Date.now() - 24 * 60 * 60 * 1000, Date.now()
      );
      const formatted = timelineEvents.map(e => ({
        id: e.id,
        type: e.type === 'earnings' ? 'price_alert' : e.type,
        symbol: e.symbols?.[0],
        message: e.title,
        timestamp: e.timestamp,
        impact: e.impact,
        regime: regime.regime,
      }));
      setEvents(formatted.reverse().slice(0, 50));
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
        return <PanelStocks data={marketData?.stocks} signals={technicals.signals} />;
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
        return <PanelChart symbol="BTC" />;
      case 'correlation':
        return <PanelCorrelation matrix={corrMatrix} symbols={CORRELATION_SYMBOLS} window={corrWindow} onWindowChange={setCorrWindow} />;
      case 'network':
        return <PanelNetwork pairs={networkPairs} symbols={networkSymbols} />;
      case 'timeline':
        return <PanelTimeline events={events} />;
      case 'company':
        return <PanelCompany />;
      case 'alerts':
        return <PanelAlerts alerts={alerts} marketData={marketData} mlState={mlEngine} patternEvents={patternEngine.events} technicalSignals={technicals.signals} />;
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
      case 'sqlQuery':
        return <PanelSqlQuery data={marketData} />;
      case 'githubTrending':
        return <PanelGithubTrending />;
      case 'huggingFace':
        return <PanelHuggingFace />;
      case 'sentiment':
        return <PanelSentiment />;
      case 'sectors':
        return <PanelSectors />;
      case 'watchlist':
        return <PanelWatchlist data={marketData} />;
      case 'defi':
        return <PanelDefi />;
      case 'cryptoGlobal':
        return <PanelCryptoGlobal />;
      case 'redditSentiment':
        return <PanelRedditSentiment />;
      case 'secFilings':
        return <PanelSECFilings />;
      case 'researchPapers':
        return <PanelResearchPapers />;
      case 'mlDashboard':
        return <PanelML mlState={mlEngine} onRetrain={mlEngine.forceRetrain} onReset={mlEngine.reset} />;
      case 'signals':
        return <PanelSignals mlState={mlEngine} />;
      case 'candlestick':
        return <PanelCandlestick />;
      case 'portfolio':
        return <PanelPortfolio data={marketData} />;
      case 'earningsCalendar':
        return <PanelEarningsCalendar />;
      default:
        return <div style={{ padding: 16, color: 'var(--text-3)', fontSize: 12 }}>Unknown panel: {panelId}</div>;
    }
  }, [marketData, corrMatrix, corrPairs, networkPairs, networkSymbols, events, alerts, patternEngine.events, technicals.signals]);

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
      <ShortcutsModal isOpen={commandBar.showShortcuts} onClose={() => commandBar.setShowShortcuts(false)} />
      <OfflineIndicator />
    </AppShell>
  );
}

export default App;
