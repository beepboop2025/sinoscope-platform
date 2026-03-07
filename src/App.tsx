import { useState, useEffect, useRef, useCallback, useMemo, lazy, Suspense, type ReactElement } from 'react';
import { ResponsiveGridLayout, useContainerWidth } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';

import AppShell from './components/layout/AppShell';
import CommandBar from './components/layout/CommandBar';
import ShortcutsModal from './components/shared/ShortcutsModal';
import WelcomeModal from './components/shared/WelcomeModal';
import { ErrorBoundary } from './components/shared/ErrorBoundary';
import OfflineIndicator from './components/shared/OfflineIndicator';
import { PanelSkeleton } from './components/shared/LoadingSkeleton';
import { startAnimationBudgetMonitor } from './utils/animationBudget';

// Lazy-loaded panels
const PanelForex = lazy(() => import('./components/panels/PanelForex'));
const PanelStocks = lazy(() => import('./components/panels/PanelStocks'));
const PanelCrypto = lazy(() => import('./components/panels/PanelCrypto'));
const PanelBonds = lazy(() => import('./components/panels/PanelBonds'));
const PanelCommodities = lazy(() => import('./components/panels/PanelCommodities'));
const PanelEconomic = lazy(() => import('./components/panels/PanelEconomic'));
const PanelNews = lazy(() => import('./components/panels/PanelNews'));
const PanelChart = lazy(() => import('./components/panels/PanelChart'));
const PanelCorrelation = lazy(() => import('./components/panels/PanelCorrelation'));
const PanelNetwork = lazy(() => import('./components/panels/PanelNetwork'));
const PanelTimeline = lazy(() => import('./components/panels/PanelTimeline'));
const PanelCompany = lazy(() => import('./components/panels/PanelCompany'));
const PanelAlerts = lazy(() => import('./components/panels/PanelAlerts'));
const PanelSqlQuery = lazy(() => import('./components/panels/PanelSqlQuery'));
const PanelGithubTrending = lazy(() => import('./components/panels/PanelGithubTrending'));
const PanelHuggingFace = lazy(() => import('./components/panels/PanelHuggingFace'));
const PanelSentiment = lazy(() => import('./components/panels/PanelSentiment'));
const PanelSectors = lazy(() => import('./components/panels/PanelSectors'));
const PanelWatchlist = lazy(() => import('./components/panels/PanelWatchlist'));
const PanelDefi = lazy(() => import('./components/panels/PanelDefi'));
const PanelCryptoGlobal = lazy(() => import('./components/panels/PanelCryptoGlobal'));
const PanelRedditSentiment = lazy(() => import('./components/panels/PanelRedditSentiment'));
const PanelSECFilings = lazy(() => import('./components/panels/PanelSECFilings'));
const PanelResearchPapers = lazy(() => import('./components/panels/PanelResearchPapers'));
const PanelML = lazy(() => import('./components/panels/PanelML'));
const PanelSignals = lazy(() => import('./components/panels/PanelSignals'));
const PanelCandlestick = lazy(() => import('./components/panels/PanelCandlestick'));
const PanelPortfolio = lazy(() => import('./components/panels/PanelPortfolio'));
const PanelEarningsCalendar = lazy(() => import('./components/panels/PanelEarningsCalendar'));

// China panels
const PanelChinaMarkets = lazy(() => import('./components/panels/china/PanelChinaMarkets'));
const PanelCNYTracker = lazy(() => import('./components/panels/china/PanelCNYTracker'));
const PanelPBOCWatch = lazy(() => import('./components/panels/china/PanelPBOCWatch'));
const PanelTradeFlow = lazy(() => import('./components/panels/china/PanelTradeFlow'));
const PanelBeltRoad = lazy(() => import('./components/panels/china/PanelBeltRoad'));
const PanelChinaCalendar = lazy(() => import('./components/panels/china/PanelChinaCalendar'));

// New panels
const PanelFundamentals = lazy(() => import('./components/panels/PanelFundamentals'));
const PanelNewsFeed = lazy(() => import('./components/panels/PanelNewsFeed'));
const PanelEconCalendar = lazy(() => import('./components/panels/PanelEconCalendar'));
const PanelScreener = lazy(() => import('./components/panels/PanelScreener'));
const PanelHeatMap = lazy(() => import('./components/panels/PanelHeatMap'));
const PanelOrderBook = lazy(() => import('./components/panels/PanelOrderBook'));
const PanelIndianMarket = lazy(() => import('./components/panels/PanelIndianMarket'));
const PanelSystemHealth = lazy(() => import('./components/panels/PanelSystemHealth'));
const PanelSettings = lazy(() => import('./components/panels/PanelSettings'));

// Engine & hooks
import { createMarketEngine } from './engine/MarketEngine';
import { useMarketData } from './hooks/useMarketData';
import { useWebSocket } from './hooks/useWebSocket';
import { useBackendWS } from './hooks/useBackendWS';
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

interface FormattedEvent {
  id: string;
  type: string;
  symbol: string | undefined;
  message: string;
  timestamp: number;
  impact: string;
  regime: string;
}

const CORRELATION_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'BTC', 'ETH', 'SOL'];

function App(): ReactElement {
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

  // Start animation budget monitor
  useEffect(() => {
    return startAnimationBudgetMonitor();
  }, []);

  const engineRef = useRef<ReturnType<typeof createMarketEngine> | null>(null);
  const [useMock, setUseMock] = useState<boolean>(false);
  const [events, setEvents] = useState<FormattedEvent[]>([]);
  const [alerts] = useState<unknown[]>([]);
  const [corrWindow, setCorrWindow] = useState<number>(30);

  // Initialize engine once
  if (!engineRef.current) {
    engineRef.current = createMarketEngine();
  }
  const engine = engineRef.current;

  // Market data from engine
  const marketData = useMarketData(engine);

  // WebSocket for real-time crypto (Binance sub-second tickers)
  useWebSocket(engine, { useMock });

  // Backend WebSocket for multi-category collector updates
  useBackendWS(engine);

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
  const timelineRef = useRef<ReturnType<typeof createTimelineEngine> | null>(null);
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

        for (const [k, v] of Object.entries(mockForex)) engine.updateFromWS({ symbol: k, ...(v as Record<string, unknown>) });
        for (const [k, v] of Object.entries(mockStocks)) engine.updateFromWS({ symbol: k, ...(v as Record<string, unknown>) });
        for (const [k, v] of Object.entries(mockCrypto)) engine.updateFromWS({ symbol: k + 'USDT', ...(v as Record<string, unknown>) });
      }
    }, 8000);
    return () => clearTimeout(timer);
  }, [engine, marketData]);

  // Generate events from market data using TimelineEngine
  const prevMarketRef = useRef<Record<string, unknown>>({});
  useEffect(() => {
    if (!marketData) return;
    const timeline = timelineRef.current;
    if (!timeline) return;
    const prev = prevMarketRef.current;
    let added = false;

    // Check stocks for significant moves
    const stocks = (marketData.stocks || {}) as Record<string, Record<string, unknown>>;
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
            title: `${sym} ${(data.changePct as number) > 0 ? 'surged' : 'dropped'} ${pct.toFixed(1)}%`,
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
    const crypto = (marketData.crypto || {}) as Record<string, Record<string, unknown>>;
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
            title: `${cleanSym} ${(data.changePct as number) > 0 ? 'rallied' : 'fell'} ${pct.toFixed(1)}%`,
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
      (prev as Record<string, unknown>)._initialized = true;
    }

    // Build timeline and convert to event format for PanelTimeline
    if (added) {
      const regime = timeline.getMarketRegime(24);
      const timelineEvents = timeline.createTimeline(
        Date.now() - 24 * 60 * 60 * 1000, Date.now()
      );
      const formatted: FormattedEvent[] = timelineEvents.map(e => ({
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
  const handleCommand = useCallback((cmd: { action: string; target?: string }) => {
    if (cmd.action === 'workspace' && cmd.target) {
      switchWorkspace(cmd.target);
    } else if (cmd.action === 'addPanel' && cmd.target) {
      addPanelToWorkspace(cmd.target);
    }
  }, [switchWorkspace, addPanelToWorkspace]);

  const commandBar = useCommandBar({ onCommand: handleCommand, marketData });

  // Layout change
  const handleLayoutChange = useCallback((layout: readonly import('./types').LayoutItem[]) => {
    updateLayout(activeId, [...layout]);
  }, [updateLayout, activeId]);

  // Render a panel by its id
  const renderPanel = useCallback((panelId: string): ReactElement => {
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
        return <PanelEconomic data={marketData?.economic as any} />;
      case 'news':
        return <PanelNews />;
      case 'chart':
        return <PanelChart symbol="BTC" />;
      case 'correlation':
        return <PanelCorrelation matrix={corrMatrix ?? undefined} symbols={CORRELATION_SYMBOLS} window={corrWindow} onWindowChange={setCorrWindow} />;
      case 'network':
        return <PanelNetwork pairs={networkPairs} symbols={networkSymbols} />;
      case 'timeline':
        return <PanelTimeline events={events} />;
      case 'company':
        return <PanelCompany />;
      case 'alerts':
        return <PanelAlerts alerts={alerts as any} marketData={marketData as any} mlState={mlEngine as any} patternEvents={patternEngine.events as any} technicalSignals={technicals.signals as any} />;
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
        return <PanelWatchlist data={marketData as any} />;
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
        return <PanelML mlState={mlEngine as any} onRetrain={mlEngine.forceRetrain} onReset={mlEngine.reset} />;
      case 'signals':
        return <PanelSignals mlState={mlEngine as any} />;
      case 'candlestick':
        return <PanelCandlestick />;
      case 'portfolio':
        return <PanelPortfolio data={marketData as any} />;
      case 'earningsCalendar':
        return <PanelEarningsCalendar />;
      case 'fundamentals':
        return <PanelFundamentals />;
      case 'newsFeed':
        return <PanelNewsFeed />;
      case 'econCalendar':
        return <PanelEconCalendar />;
      case 'screener':
        return <PanelScreener />;
      case 'heatMap':
        return <PanelHeatMap />;
      case 'orderBook':
        return <PanelOrderBook />;
      case 'indianMarket':
        return <PanelIndianMarket />;
      case 'systemHealth':
        return <PanelSystemHealth />;
      case 'settings':
        return <PanelSettings />;
      default:
        return <div style={{ padding: 16, color: 'var(--text-3)', fontSize: 12 }}>Unknown panel: {panelId}</div>;
    }
  }, [marketData, corrMatrix, corrPairs, corrWindow, setCorrWindow, networkPairs, networkSymbols, events, alerts, patternEngine.events, technicals.signals, mlEngine]);

  const layout = activeWorkspace?.layout || [];
  const panels = activeWorkspace?.panels || [];

  const { containerRef: gridRef, width: containerWidth, mounted: gridMounted } = useContainerWidth();

  return (
    <AppShell
      marketData={marketData}
      wsStatus={useMock ? 'mock' : 'live'}
      workspace={workspace as any}
      onOpenCommandBar={() => commandBar.setIsOpen(true)}
      panelCount={panels.length}
      onShowShortcuts={() => commandBar.setShowShortcuts(true)}
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
            dragConfig={{ enabled: true, bounded: false, handle: '.panel-titlebar' }}
            onLayoutChange={handleLayoutChange as any}
            margin={[8, 8]}
          >
            {panels.map((panelId: string) => (
              <div key={panelId}>
                <ErrorBoundary>
                  <Suspense fallback={<PanelSkeleton />}>
                    {renderPanel(panelId)}
                  </Suspense>
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
        filtered={commandBar.filtered as any}
        activeIndex={commandBar.activeIndex}
        setActiveIndex={commandBar.setActiveIndex}
        execute={commandBar.execute}
        handleKeyDown={commandBar.handleKeyDown}
        onClose={() => commandBar.setIsOpen(false)}
      />
      <ShortcutsModal isOpen={commandBar.showShortcuts} onClose={() => commandBar.setShowShortcuts(false)} />
      <OfflineIndicator />
      <WelcomeModal />
    </AppShell>
  );
}

export default App;
