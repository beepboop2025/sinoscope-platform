import React, { useState, useCallback, useEffect, useRef } from 'react';
import { 
  LayoutDashboard, 
  CandlestickChart, 
  BookOpen, 
  Newspaper, 
  List, 
  Settings, 
  Search,
  Maximize2,
  Minimize2,
  X,
  GripVertical,
  ChevronLeft,
  ChevronRight,
  Command,
  Plus,
  MoreHorizontal,
  Pin,
  PinOff,
  Layers,
  Activity,
  TrendingUp,
  BarChart3,
  Bell,
  User,
  LogOut,
  Monitor,
  Moon,
  Sun,
} from 'lucide-react';
import { useTerminalStore, useWatchlistStore } from '../stores/terminalStore';
import { clsx, tw } from '../utils/styles';
import PriceChartPro from './PriceChartPro';
import OrderBook from './OrderBook';
import WatchlistPro from './WatchlistPro';
import NewsFeed from './NewsFeed';

// Command Palette Component
const CommandPalette = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const { addPanel, panels, setActivePanel } = useTerminalStore();
  const { symbols, addSymbol } = useWatchlistStore();

  const commands = [
    { id: 'new-chart', label: 'New Chart Panel', icon: CandlestickChart, action: () => {
      addPanel({ type: 'chart', title: 'Chart', symbol: 'AAPL', timeframe: '1D' });
      onClose();
    }},
    { id: 'new-watchlist', label: 'New Watchlist Panel', icon: List, action: () => {
      addPanel({ type: 'watchlist', title: 'Watchlist' });
      onClose();
    }},
    { id: 'new-orderbook', label: 'New Order Book Panel', icon: BookOpen, action: () => {
      addPanel({ type: 'orderbook', title: 'Order Book', symbol: 'AAPL' });
      onClose();
    }},
    { id: 'new-news', label: 'New News Panel', icon: Newspaper, action: () => {
      addPanel({ type: 'news', title: 'News Feed' });
      onClose();
    }},
    { id: 'toggle-sidebar', label: 'Toggle Sidebar', icon: LayoutDashboard, action: () => {
      useTerminalStore.getState().toggleSidebar();
      onClose();
    }},
    { id: 'add-symbol', label: 'Add Symbol to Watchlist...', icon: Plus, action: () => {
      // Would open symbol search
      onClose();
    }},
    ...symbols.map(s => ({
      id: `chart-${s}`,
      label: `Open Chart: ${s}`,
      icon: TrendingUp,
      action: () => {
        addPanel({ type: 'chart', title: `${s} Chart`, symbol: s, timeframe: '1D' });
        onClose();
      }
    })),
  ];

  const filteredCommands = commands.filter(cmd => 
    cmd.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      inputRef.current?.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;
      
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(i => Math.min(i + 1, filteredCommands.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(i => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].action();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-lg shadow-2xl overflow-hidden">
        <div className="flex items-center gap-3 p-4 border-b border-slate-800">
          <Search className="w-5 h-5 text-slate-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 outline-none text-lg"
          />
          <kbd className="px-2 py-1 text-xs bg-slate-800 text-slate-400 rounded">ESC</kbd>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {filteredCommands.map((cmd, idx) => {
            const Icon = cmd.icon;
            return (
              <button
                key={cmd.id}
                onClick={cmd.action}
                className={tw(
                  "w-full flex items-center gap-3 px-4 py-3 text-left transition-colors",
                  idx === selectedIndex ? "bg-blue-600/20 text-blue-400" : "text-slate-300 hover:bg-slate-800"
                )}
              >
                <Icon className="w-5 h-5" />
                <span className="flex-1">{cmd.label}</span>
                {idx === selectedIndex && <kbd className="text-xs text-slate-500">↵</kbd>}
              </button>
            );
          })}
          {filteredCommands.length === 0 && (
            <div className="p-8 text-center text-slate-500">
              No commands found matching "{query}"
            </div>
          )}
        </div>
        <div className="flex items-center gap-4 px-4 py-2 bg-slate-950 border-t border-slate-800 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-slate-800 rounded">↑↓</kbd> to navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-slate-800 rounded">↵</kbd> to select
          </span>
        </div>
      </div>
    </div>
  );
};

// Panel Component
const Panel = ({ panel, isActive, onActivate, onClose, onDetach, onMaximize, isMaximized }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const [showTabs, setShowTabs] = useState(false);
  const [tabs, setTabs] = useState([{ id: panel.id, title: panel.title, type: panel.type }]);
  const [activeTab, setActiveTab] = useState(0);

  const renderContent = () => {
    const currentPanel = tabs[activeTab];
    switch (currentPanel.type) {
      case 'chart':
        return <PriceChartPro symbol={currentPanel.symbol} timeframe={currentPanel.timeframe} panelId={currentPanel.id} />;
      case 'orderbook':
        return <OrderBook symbol={currentPanel.symbol} />;
      case 'watchlist':
        return <WatchlistPro />;
      case 'news':
        return <NewsFeed />;
      default:
        return <div className="flex items-center justify-center h-full text-slate-500">Unknown panel type</div>;
    }
  };

  return (
    <div 
      className={tw(
        "flex flex-col h-full bg-slate-900 border border-slate-700 rounded-lg overflow-hidden",
        isActive ? "ring-1 ring-blue-500/50" : "",
        isMaximized ? "fixed inset-4 z-40" : ""
      )}
      onClick={onActivate}
    >
      {/* Panel Header */}
      <div 
        className={tw(
          "flex items-center gap-2 px-3 py-2 bg-slate-800/50 border-b border-slate-700/50 select-none",
          isDragging ? "cursor-grabbing" : "cursor-grab"
        )}
        onMouseDown={() => setIsDragging(true)}
        onMouseUp={() => setIsDragging(false)}
        onMouseLeave={() => setIsDragging(false)}
      >
        <GripVertical className="w-4 h-4 text-slate-600" />
        
        {/* Tabs */}
        <div className="flex-1 flex items-center gap-1 overflow-hidden">
          {tabs.map((tab, idx) => (
            <button
              key={tab.id}
              onClick={(e) => { e.stopPropagation(); setActiveTab(idx); }}
              className={tw(
                "px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-2 min-w-0",
                activeTab === idx 
                  ? "bg-slate-700 text-slate-100" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
              )}
            >
              {tab.type === 'chart' && <CandlestickChart className="w-3.5 h-3.5 shrink-0" />}
              {tab.type === 'orderbook' && <BookOpen className="w-3.5 h-3.5 shrink-0" />}
              {tab.type === 'watchlist' && <List className="w-3.5 h-3.5 shrink-0" />}
              {tab.type === 'news' && <Newspaper className="w-3.5 h-3.5 shrink-0" />}
              <span className="truncate">{tab.title}</span>
              {tabs.length > 1 && (
                <X 
                  className="w-3 h-3 hover:text-red-400 shrink-0" 
                  onClick={(e) => { 
                    e.stopPropagation(); 
                    setTabs(t => t.filter((_, i) => i !== idx));
                    if (activeTab >= idx && activeTab > 0) setActiveTab(activeTab - 1);
                  }}
                />
              )}
            </button>
          ))}
        </div>

        {/* Panel Actions */}
        <div className="flex items-center gap-1">
          <button 
            onClick={(e) => { e.stopPropagation(); setIsPinned(!isPinned); }}
            className={tw(
              "p-1.5 rounded hover:bg-slate-700 transition-colors",
              isPinned ? "text-blue-400" : "text-slate-400"
            )}
            title={isPinned ? "Unpin panel" : "Pin panel"}
          >
            {isPinned ? <Pin className="w-4 h-4" /> : <PinOff className="w-4 h-4" />}
          </button>
          <button 
            onClick={(e) => { e.stopPropagation(); onMaximize(); }}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-400 transition-colors"
            title={isMaximized ? "Restore" : "Maximize"}
          >
            {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button 
            onClick={(e) => { e.stopPropagation(); onDetach(); }}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-400 transition-colors"
            title="Pop out"
          >
            <Monitor className="w-4 h-4" />
          </button>
          <button 
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            className="p-1.5 rounded hover:bg-red-500/20 hover:text-red-400 text-slate-400 transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Panel Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {renderContent()}
      </div>
    </div>
  );
};

// Sidebar Component
const Sidebar = ({ collapsed, onToggle }) => {
  const { addPanel, panels } = useTerminalStore();
  const [activeSection, setActiveSection] = useState('main');

  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard', action: () => {} },
    { id: 'charts', icon: CandlestickChart, label: 'Charts', action: () => addPanel({ type: 'chart', title: 'Chart', symbol: 'AAPL', timeframe: '1D' }) },
    { id: 'watchlist', icon: List, label: 'Watchlist', action: () => addPanel({ type: 'watchlist', title: 'Watchlist' }) },
    { id: 'orderbook', icon: BookOpen, label: 'Order Book', action: () => addPanel({ type: 'orderbook', title: 'Order Book', symbol: 'AAPL' }) },
    { id: 'news', icon: Newspaper, label: 'News', action: () => addPanel({ type: 'news', title: 'News Feed' }) },
    { id: 'screener', icon: BarChart3, label: 'Screener', action: () => {} },
    { id: 'alerts', icon: Bell, label: 'Alerts', action: () => {} },
    { id: 'activity', icon: Activity, label: 'Activity', action: () => {} },
  ];

  const workspaceItems = [
    { id: 'ws1', label: 'Day Trading', icon: Layers },
    { id: 'ws2', label: 'Swing Trading', icon: Layers },
    { id: 'ws3', label: 'Research', icon: Layers },
  ];

  return (
    <div 
      className={tw(
        "flex flex-col bg-slate-900 border-r border-slate-800 transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-slate-800">
        <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center shrink-0">
          <span className="text-white font-bold text-sm">DS</span>
        </div>
        {!collapsed && (
          <div className="flex-1 min-w-0">
            <h1 className="text-slate-100 font-semibold text-sm truncate">DragonScope</h1>
            <p className="text-slate-500 text-xs truncate">Enterprise</p>
          </div>
        )}
        <button 
          onClick={onToggle}
          className="p-1 rounded hover:bg-slate-800 text-slate-400"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Main Menu */}
      <div className="flex-1 overflow-y-auto py-2">
        <div className={tw("px-2 mb-2", collapsed ? "hidden" : "block")}>
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider px-2">Tools</span>
        </div>
        {menuItems.map(item => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={item.action}
              className={tw(
                "w-full flex items-center gap-3 px-3 py-2.5 text-sm transition-colors hover:bg-slate-800/50 group",
                collapsed ? "justify-center" : ""
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 text-slate-400 group-hover:text-blue-400 shrink-0" />
              {!collapsed && <span className="text-slate-300 group-hover:text-slate-100">{item.label}</span>}
            </button>
          );
        })}

        {/* Workspaces */}
        {!collapsed && (
          <>
            <div className="px-2 mt-6 mb-2">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider px-2">Workspaces</span>
            </div>
            {workspaceItems.map(item => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </>
        )}
      </div>

      {/* Bottom Actions */}
      <div className="border-t border-slate-800 p-2">
        <button className={tw(
          "w-full flex items-center gap-3 px-3 py-2.5 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors rounded-lg",
          collapsed ? "justify-center" : ""
        )}>
          <Settings className="w-5 h-5" />
          {!collapsed && <span>Settings</span>}
        </button>
        <button className={tw(
          "w-full flex items-center gap-3 px-3 py-2.5 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors rounded-lg",
          collapsed ? "justify-center" : ""
        )}>
          <User className="w-5 h-5" />
          {!collapsed && <span>Profile</span>}
        </button>
      </div>
    </div>
  );
};

// Top Bar Component
const TopBar = ({ onCommandPalette }) => {
  const { connections, lastPrices } = useTerminalStore();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-800">
      {/* Left: Command Palette Trigger */}
      <button
        onClick={onCommandPalette}
        className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 rounded-md text-sm text-slate-400 transition-colors"
      >
        <Search className="w-4 h-4" />
        <span className="hidden sm:inline">Command Palette</span>
        <kbd className="hidden md:flex items-center gap-0.5 px-1.5 py-0.5 bg-slate-700 rounded text-xs">
          <Command className="w-3 h-3" />
          <span>K</span>
        </kbd>
      </button>

      {/* Center: Connection Status & Market Status */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className={tw(
            "w-2 h-2 rounded-full",
            connections.marketData ? "bg-green-500 animate-pulse" : "bg-red-500"
          )} />
          <span className="text-slate-400">Market Data</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={tw(
            "w-2 h-2 rounded-full",
            connections.news ? "bg-green-500 animate-pulse" : "bg-red-500"
          )} />
          <span className="text-slate-400">News</span>
        </div>
        <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-slate-800/50 rounded-full">
          <span className="text-green-400">●</span>
          <span className="text-slate-300">Market Open</span>
        </div>
      </div>

      {/* Right: Time & User */}
      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-400 font-mono">
          {currentTime.toLocaleTimeString('en-US', { hour12: false })}
        </span>
        <span className="text-xs text-slate-500">
          {currentTime.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
        </span>
      </div>
    </div>
  );
};

// Grid Layout System
const GridLayout = ({ panels, activePanel, onActivate, onClose, onDetach }) => {
  const [maximizedPanel, setMaximizedPanel] = useState(null);

  if (panels.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500">
        <LayoutDashboard className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg mb-2">No panels open</p>
        <p className="text-sm">Use the sidebar or press Cmd+K to add panels</p>
      </div>
    );
  }

  // Simple grid layout based on panel count
  const getGridClass = () => {
    if (maximizedPanel) return "grid-cols-1";
    const count = panels.filter(p => !p.detached).length;
    if (count === 1) return "grid-cols-1";
    if (count === 2) return "grid-cols-2";
    if (count === 3) return "grid-cols-2";
    if (count === 4) return "grid-cols-2 grid-rows-2";
    return "grid-cols-3 grid-rows-2";
  };

  const visiblePanels = panels.filter(p => !p.detached);

  return (
    <div className={tw("grid gap-3 p-3 h-full", getGridClass())}>
      {visiblePanels.map(panel => (
        <Panel
          key={panel.id}
          panel={panel}
          isActive={activePanel === panel.id}
          onActivate={() => onActivate(panel.id)}
          onClose={() => onClose(panel.id)}
          onDetach={() => onDetach(panel.id)}
          onMaximize={() => setMaximizedPanel(maximizedPanel === panel.id ? null : panel.id)}
          isMaximized={maximizedPanel === panel.id}
        />
      ))}
    </div>
  );
};

// Main Terminal Layout Component
const TerminalLayout = () => {
  const {
    sidebarCollapsed,
    toggleSidebar,
    panels,
    activePanel,
    setActivePanel,
    removePanel,
    detachPanel,
    commandPaletteOpen,
    toggleCommandPalette,
    setCommandPaletteOpen,
  } = useTerminalStore();

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Cmd/Ctrl + K
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggleCommandPalette();
      }
      // Cmd/Ctrl + B
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen w-screen bg-slate-950 overflow-hidden">
      {/* Command Palette */}
      <CommandPalette 
        isOpen={commandPaletteOpen} 
        onClose={() => setCommandPaletteOpen(false)} 
      />

      {/* Sidebar */}
      <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar onCommandPalette={toggleCommandPalette} />
        
        <div className="flex-1 min-h-0 overflow-hidden">
          <GridLayout
            panels={panels}
            activePanel={activePanel}
            onActivate={setActivePanel}
            onClose={removePanel}
            onDetach={detachPanel}
          />
        </div>
      </div>
    </div>
  );
};

export default TerminalLayout;
