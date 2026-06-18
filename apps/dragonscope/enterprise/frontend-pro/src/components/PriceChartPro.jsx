import React, { useEffect, useRef, useState, useCallback } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  BarChart3, 
  LineChart, 
  CandlestickChart,
  Activity,
  Settings,
  Maximize2,
  Plus,
  Minus,
  Crosshair,
  Pencil,
  Trash2,
  Type,
  Minus as LineIcon,
  BoxSelect,
  Layers,
  X,
  ChevronDown,
  MoreHorizontal,
  Move,
  Expand,
  Scan,
  RefreshCw,
  Download,
  Camera,
  Eye,
  EyeOff,
} from 'lucide-react';
import { useChartStore, useTerminalStore } from '../stores/terminalStore';
import { 
  generateChartData, 
  calculateSMA, 
  calculateEMA, 
  calculateBollinger, 
  calculateRSI, 
  calculateMACD,
  toHeikinAshi,
  formatPrice,
  formatNumber,
  tw,
} from '../utils/styles';

// Timeframes
const TIMEFRAMES = [
  { id: '1m', label: '1m', seconds: 60 },
  { id: '5m', label: '5m', seconds: 300 },
  { id: '15m', label: '15m', seconds: 900 },
  { id: '1h', label: '1H', seconds: 3600 },
  { id: '4h', label: '4H', seconds: 14400 },
  { id: '1D', label: 'D', seconds: 86400 },
  { id: '1W', label: 'W', seconds: 604800 },
  { id: '1M', label: 'M', seconds: 2592000 },
];

// Chart Types
const CHART_TYPES = [
  { id: 'candlestick', label: 'Candles', icon: CandlestickChart },
  { id: 'line', label: 'Line', icon: LineChart },
  { id: 'area', label: 'Area', icon: Activity },
  { id: 'bar', label: 'Bars', icon: BarChart3 },
  { id: 'heikin-ashi', label: 'Heikin-Ashi', icon: Layers },
];

// Technical Indicators
const INDICATORS = [
  { id: 'sma20', label: 'SMA 20', type: 'overlay', color: '#2962FF' },
  { id: 'sma50', label: 'SMA 50', type: 'overlay', color: '#FF6D00' },
  { id: 'sma200', label: 'SMA 200', type: 'overlay', color: '#E91E63' },
  { id: 'ema12', label: 'EMA 12', type: 'overlay', color: '#00C853' },
  { id: 'ema26', label: 'EMA 26', type: 'overlay', color: '#FFD600' },
  { id: 'bollinger', label: 'Bollinger Bands', type: 'overlay', color: '#7C4DFF' },
  { id: 'volume', label: 'Volume', type: 'panel', color: '#26A69A' },
  { id: 'rsi', label: 'RSI', type: 'panel', color: '#EC407A' },
  { id: 'macd', label: 'MACD', type: 'panel', color: '#AB47BC' },
];

// Drawing Tools
const DRAWING_TOOLS = [
  { id: 'trendline', label: 'Trend Line', icon: LineIcon },
  { id: 'horizontal', label: 'Horizontal', icon: Minus },
  { id: 'fibonacci', label: 'Fibonacci', icon: Activity },
  { id: 'rectangle', label: 'Rectangle', icon: BoxSelect },
  { id: 'text', label: 'Text', icon: Type },
  { id: 'crosshair', label: 'Measure', icon: Crosshair },
];

const PriceChartPro = ({ symbol = 'AAPL', timeframe: initialTimeframe = '1D', panelId }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candlestickSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const indicatorSeriesRef = useRef({});
  const { LightweightCharts } = window;
  
  const { getChartConfig, updateChartConfig, addIndicator, removeIndicator, addComparison, removeComparison, addDrawing } = useChartStore();
  const config = getChartConfig(panelId);
  
  const [timeframe, setTimeframe] = useState(config.timeframe || initialTimeframe);
  const [chartType, setChartType] = useState(config.type || 'candlestick');
  const [activeIndicators, setActiveIndicators] = useState(config.indicators || ['volume']);
  const [compareSymbols, setCompareSymbols] = useState(config.compareSymbols || []);
  const [activeDrawingTool, setActiveDrawingTool] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [chartData, setChartData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hoverData, setHoverData] = useState(null);
  const [showToolbar, setShowToolbar] = useState(true);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current || !window.LightweightCharts) return;

    const { createChart, CrosshairMode } = window.LightweightCharts;
    
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#0f172a' },
        textColor: '#94a3b8',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      grid: {
        vertLines: { color: '#1e293b', style: 1 },
        horzLines: { color: '#1e293b', style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#3b82f6',
          labelBackgroundColor: '#3b82f6',
        },
        horzLine: {
          color: '#3b82f6',
          labelBackgroundColor: '#3b82f6',
        },
      },
      rightPriceScale: {
        borderColor: '#334155',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: '#334155',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: {
        vertTouchDrag: false,
      },
    });

    chartRef.current = chart;

    // Create main series based on chart type
    let mainSeries;
    if (chartType === 'candlestick' || chartType === 'heikin-ashi') {
      mainSeries = chart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
        borderUpColor: '#10b981',
        borderDownColor: '#ef4444',
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
      });
    } else if (chartType === 'line') {
      mainSeries = chart.addLineSeries({
        color: '#3b82f6',
        lineWidth: 2,
      });
    } else if (chartType === 'area') {
      mainSeries = chart.addAreaSeries({
        lineColor: '#3b82f6',
        topColor: '#3b82f6',
        bottomColor: 'rgba(59, 130, 246, 0.1)',
        lineWidth: 2,
      });
    } else if (chartType === 'bar') {
      mainSeries = chart.addBarSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
      });
    }

    candlestickSeriesRef.current = mainSeries;

    // Create volume series
    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    // Subscribe to crosshair move
    chart.subscribeCrosshairMove((param) => {
      if (param.time && param.point && param.point.x >= 0 && param.point.y >= 0) {
        const data = param.seriesData.get(mainSeries);
        setHoverData({
          time: param.time,
          ...data,
        });
      }
    });

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  // Load data
  useEffect(() => {
    setIsLoading(true);
    // Simulate API call
    setTimeout(() => {
      const data = generateChartData(200, Math.random() * 100 + 100);
      setChartData(data);
      setIsLoading(false);
    }, 500);
  }, [symbol, timeframe]);

  // Update chart data
  useEffect(() => {
    if (!candlestickSeriesRef.current || chartData.length === 0) return;

    const series = candlestickSeriesRef.current;
    
    let displayData = chartData;
    if (chartType === 'heikin-ashi') {
      displayData = toHeikinAshi(chartData);
    } else if (chartType === 'line') {
      displayData = chartData.map(d => ({ time: d.time, value: d.close }));
    } else if (chartType === 'area') {
      displayData = chartData.map(d => ({ time: d.time, value: d.close }));
    }

    series.setData(displayData);

    // Update volume
    if (volumeSeriesRef.current && activeIndicators.includes('volume')) {
      const volumeData = chartData.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? '#26a69a' : '#ef5350',
      }));
      volumeSeriesRef.current.setData(volumeData);
    }

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [chartData, chartType]);

  // Update indicators
  useEffect(() => {
    if (!chartRef.current || chartData.length === 0) return;

    // Clear existing indicator series
    Object.values(indicatorSeriesRef.current).forEach(series => {
      chartRef.current.removeSeries(series);
    });
    indicatorSeriesRef.current = {};

    // Add new indicators
    activeIndicators.forEach(indicatorId => {
      const indicator = INDICATORS.find(i => i.id === indicatorId);
      if (!indicator) return;

      if (indicator.type === 'overlay') {
        let data;
        let series;

        if (indicatorId.startsWith('sma')) {
          const period = parseInt(indicatorId.replace('sma', ''));
          data = calculateSMA(chartData, period);
          series = chartRef.current.addLineSeries({
            color: indicator.color,
            lineWidth: 1,
            title: indicator.label,
          });
        } else if (indicatorId.startsWith('ema')) {
          const period = parseInt(indicatorId.replace('ema', ''));
          data = calculateEMA(chartData, period);
          series = chartRef.current.addLineSeries({
            color: indicator.color,
            lineWidth: 1,
            title: indicator.label,
          });
        } else if (indicatorId === 'bollinger') {
          const bbData = calculateBollinger(chartData);
          
          const upperSeries = chartRef.current.addLineSeries({
            color: indicator.color,
            lineWidth: 1,
            title: 'BB Upper',
          });
          upperSeries.setData(bbData.map(d => ({ time: d.time, value: d.upper })));
          indicatorSeriesRef.current['bb-upper'] = upperSeries;

          const lowerSeries = chartRef.current.addLineSeries({
            color: indicator.color,
            lineWidth: 1,
            title: 'BB Lower',
          });
          lowerSeries.setData(bbData.map(d => ({ time: d.time, value: d.lower })));
          indicatorSeriesRef.current['bb-lower'] = lowerSeries;

          const middleSeries = chartRef.current.addLineSeries({
            color: '#78909c',
            lineWidth: 1,
            title: 'BB Middle',
          });
          middleSeries.setData(bbData.map(d => ({ time: d.time, value: d.middle })));
          indicatorSeriesRef.current['bb-middle'] = middleSeries;
          return;
        }

        if (series && data) {
          series.setData(data);
          indicatorSeriesRef.current[indicatorId] = series;
        }
      } else if (indicator.type === 'panel') {
        // Add panel indicators (RSI, MACD)
        if (indicatorId === 'rsi') {
          const rsiData = calculateRSI(chartData);
          const rsiSeries = chartRef.current.addLineSeries({
            color: indicator.color,
            lineWidth: 1,
            priceScaleId: 'rsi',
          });
          rsiSeries.priceScale().applyOptions({
            scaleMargins: {
              top: 0.05,
              bottom: 0.05,
            },
          });
          rsiSeries.setData(rsiData);
          indicatorSeriesRef.current['rsi'] = rsiSeries;
        } else if (indicatorId === 'macd') {
          const macdData = calculateMACD(chartData);
          
          const macdLine = chartRef.current.addLineSeries({
            color: '#2962FF',
            lineWidth: 1,
            priceScaleId: 'macd',
          });
          macdLine.priceScale().applyOptions({
            scaleMargins: {
              top: 0.05,
              bottom: 0.05,
            },
          });
          macdLine.setData(macdData.map(d => ({ time: d.time, value: d.macd })));
          indicatorSeriesRef.current['macd-line'] = macdLine;

          const signalLine = chartRef.current.addLineSeries({
            color: '#FF6D00',
            lineWidth: 1,
            priceScaleId: 'macd',
          });
          signalLine.setData(macdData.map(d => ({ time: d.time, value: d.signal })));
          indicatorSeriesRef.current['macd-signal'] = signalLine;
        }
      }
    });

    // Toggle volume visibility
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({
        visible: activeIndicators.includes('volume'),
      });
    }
  }, [activeIndicators, chartData]);

  // Update store when config changes
  useEffect(() => {
    updateChartConfig(panelId, {
      timeframe,
      type: chartType,
      indicators: activeIndicators,
      compareSymbols,
    });
  }, [timeframe, chartType, activeIndicators, compareSymbols]);

  const toggleIndicator = (indicatorId) => {
    setActiveIndicators(prev => {
      if (prev.includes(indicatorId)) {
        removeIndicator(panelId, indicatorId);
        return prev.filter(i => i !== indicatorId);
      } else {
        addIndicator(panelId, indicatorId);
        return [...prev, indicatorId];
      }
    });
  };

  const lastPrice = chartData[chartData.length - 1];
  const priceChange = lastPrice ? lastPrice.close - lastPrice.open : 0;
  const priceChangePercent = lastPrice ? (priceChange / lastPrice.open) * 100 : 0;

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-4">
          {/* Symbol Info */}
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-100">{symbol}</h2>
            {lastPrice && (
              <div className="flex items-center gap-2">
                <span className="text-lg font-mono text-slate-100">{formatPrice(lastPrice.close)}</span>
                <span className={tw(
                  "text-sm font-mono",
                  priceChange >= 0 ? "text-green-400" : "text-red-400"
                )}>
                  {priceChange >= 0 ? '+' : ''}{formatPrice(priceChange)} ({priceChangePercent.toFixed(2)}%)
                </span>
              </div>
            )}
          </div>

          {/* Timeframes */}
          <div className="flex items-center gap-0.5 bg-slate-800/50 rounded-lg p-0.5">
            {TIMEFRAMES.map(tf => (
              <button
                key={tf.id}
                onClick={() => setTimeframe(tf.id)}
                className={tw(
                  "px-2 py-1 text-xs font-medium rounded transition-colors",
                  timeframe === tf.id
                    ? "bg-slate-700 text-slate-100"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
                )}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        {/* Chart Controls */}
        <div className="flex items-center gap-2">
          {/* Chart Types */}
          <div className="flex items-center gap-0.5 bg-slate-800/50 rounded-lg p-0.5">
            {CHART_TYPES.map(type => {
              const Icon = type.icon;
              return (
                <button
                  key={type.id}
                  onClick={() => setChartType(type.id)}
                  className={tw(
                    "p-1.5 rounded transition-colors",
                    chartType === type.id
                      ? "bg-slate-700 text-blue-400"
                      : "text-slate-400 hover:text-slate-200"
                  )}
                  title={type.label}
                >
                  <Icon className="w-4 h-4" />
                </button>
              );
            })}
          </div>

          {/* Indicators Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={tw(
                "flex items-center gap-1 px-2 py-1.5 rounded text-sm transition-colors",
                showSettings || activeIndicators.length > 1
                  ? "bg-blue-600/20 text-blue-400"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              )}
            >
              <Scan className="w-4 h-4" />
              <span className="hidden sm:inline">Indicators</span>
              {activeIndicators.length > 1 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-blue-600 text-white rounded-full">
                  {activeIndicators.length - 1}
                </span>
              )}
              <ChevronDown className="w-3 h-3" />
            </button>

            {showSettings && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-50">
                <div className="p-2 border-b border-slate-800">
                  <span className="text-xs font-medium text-slate-500 uppercase">Overlays</span>
                </div>
                {INDICATORS.filter(i => i.type === 'overlay').map(indicator => (
                  <button
                    key={indicator.id}
                    onClick={() => toggleIndicator(indicator.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-800 transition-colors"
                  >
                    <div 
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: indicator.color }}
                    />
                    <span className={tw(
                      "flex-1 text-left",
                      activeIndicators.includes(indicator.id) ? "text-slate-100" : "text-slate-400"
                    )}>
                      {indicator.label}
                    </span>
                    {activeIndicators.includes(indicator.id) && (
                      <Eye className="w-4 h-4 text-blue-400" />
                    )}
                  </button>
                ))}
                <div className="p-2 border-t border-b border-slate-800">
                  <span className="text-xs font-medium text-slate-500 uppercase">Panels</span>
                </div>
                {INDICATORS.filter(i => i.type === 'panel').map(indicator => (
                  <button
                    key={indicator.id}
                    onClick={() => toggleIndicator(indicator.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-800 transition-colors"
                  >
                    <div 
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: indicator.color }}
                    />
                    <span className={tw(
                      "flex-1 text-left",
                      activeIndicators.includes(indicator.id) ? "text-slate-100" : "text-slate-400"
                    )}>
                      {indicator.label}
                    </span>
                    {activeIndicators.includes(indicator.id) && (
                      <Eye className="w-4 h-4 text-blue-400" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Drawing Tools */}
          <div className="flex items-center gap-0.5 bg-slate-800/50 rounded-lg p-0.5">
            {DRAWING_TOOLS.map(tool => {
              const Icon = tool.icon;
              return (
                <button
                  key={tool.id}
                  onClick={() => setActiveDrawingTool(activeDrawingTool === tool.id ? null : tool.id)}
                  className={tw(
                    "p-1.5 rounded transition-colors",
                    activeDrawingTool === tool.id
                      ? "bg-blue-600/20 text-blue-400"
                      : "text-slate-400 hover:text-slate-200"
                  )}
                  title={tool.label}
                >
                  <Icon className="w-4 h-4" />
                </button>
              );
            })}
          </div>

          {/* Chart Actions */}
          <div className="flex items-center gap-0.5">
            <button 
              className="p-1.5 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button 
              className="p-1.5 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800"
              title="Screenshot"
            >
              <Camera className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Chart Container */}
      <div className="flex-1 min-h-0 relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 z-10">
            <div className="flex items-center gap-2 text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin" />
              <span>Loading...</span>
            </div>
          </div>
        )}
        
        <div ref={chartContainerRef} className="w-full h-full" />

        {/* Crosshair Info */}
        {hoverData && (
          <div className="absolute top-2 left-2 bg-slate-900/90 border border-slate-700 rounded-lg p-2 text-xs font-mono z-10">
            <div className="text-slate-400 mb-1">{hoverData.time}</div>
            {'open' in hoverData && (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">O:</span>
                  <span className="text-slate-200">{formatPrice(hoverData.open)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">H:</span>
                  <span className="text-slate-200">{formatPrice(hoverData.high)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">L:</span>
                  <span className="text-slate-200">{formatPrice(hoverData.low)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">C:</span>
                  <span className={hoverData.close >= hoverData.open ? 'text-green-400' : 'text-red-400'}>
                    {formatPrice(hoverData.close)}
                  </span>
                </div>
              </>
            )}
            {'value' in hoverData && (
              <div className="flex items-center gap-2">
                <span className="text-slate-500">Value:</span>
                <span className="text-slate-200">{formatPrice(hoverData.value)}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Comparison Panel */}
      {compareSymbols.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 border-t border-slate-800 bg-slate-900/50">
          <span className="text-xs text-slate-500">Compare:</span>
          {compareSymbols.map(sym => (
            <span key={sym} className="flex items-center gap-1 px-2 py-1 bg-slate-800 rounded text-xs text-slate-300">
              {sym}
              <X 
                className="w-3 h-3 cursor-pointer hover:text-red-400" 
                onClick={() => setCompareSymbols(prev => prev.filter(s => s !== sym))}
              />
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default PriceChartPro;
