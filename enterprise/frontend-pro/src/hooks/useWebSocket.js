import { useEffect, useRef, useState, useCallback } from 'react';
import { useTerminalStore } from '../stores/terminalStore';

/**
 * Custom hook for WebSocket connections with auto-reconnect
 * @param {string} url - WebSocket URL
 * @param {Object} options - Configuration options
 */
export const useWebSocket = (url, options = {}) => {
  const {
    onOpen,
    onMessage,
    onClose,
    onError,
    reconnectInterval = 3000,
    reconnectAttempts = 5,
    heartbeatInterval = 30000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [readyState, setReadyState] = useState(WebSocket.CONNECTING);
  
  const ws = useRef(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef(null);
  const heartbeatTimer = useRef(null);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    try {
      ws.current = new WebSocket(url);
      setReadyState(WebSocket.CONNECTING);

      ws.current.onopen = (event) => {
        setIsConnected(true);
        setReadyState(WebSocket.OPEN);
        reconnectCount.current = 0;
        onOpen?.(event);

        // Start heartbeat
        if (heartbeatInterval > 0) {
          heartbeatTimer.current = setInterval(() => {
            if (ws.current?.readyState === WebSocket.OPEN) {
              ws.current.send(JSON.stringify({ type: 'ping' }));
            }
          }, heartbeatInterval);
        }
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          onMessage?.(data, event);
        } catch {
          setLastMessage(event.data);
          onMessage?.(event.data, event);
        }
      };

      ws.current.onclose = (event) => {
        setIsConnected(false);
        setReadyState(WebSocket.CLOSED);
        onClose?.(event);

        // Clear heartbeat
        if (heartbeatTimer.current) {
          clearInterval(heartbeatTimer.current);
          heartbeatTimer.current = null;
        }

        // Attempt reconnection
        if (reconnectCount.current < reconnectAttempts) {
          reconnectCount.current += 1;
          reconnectTimer.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      ws.current.onerror = (event) => {
        setReadyState(WebSocket.CLOSED);
        onError?.(event);
      };
    } catch (error) {
      onError?.(error);
    }
  }, [url, onOpen, onMessage, onClose, onError, reconnectInterval, reconnectAttempts, heartbeatInterval]);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
  }, []);

  const sendMessage = useCallback((data) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      ws.current.send(message);
      return true;
    }
    return false;
  }, []);

  const subscribe = useCallback((channel, symbols) => {
    return sendMessage({
      type: 'subscribe',
      channel,
      symbols,
    });
  }, [sendMessage]);

  const unsubscribe = useCallback((channel, symbols) => {
    return sendMessage({
      type: 'unsubscribe',
      channel,
      symbols,
    });
  }, [sendMessage]);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return {
    isConnected,
    readyState,
    lastMessage,
    sendMessage,
    subscribe,
    unsubscribe,
    connect,
    disconnect,
  };
};

/**
 * Hook for market data WebSocket connection
 */
export const useMarketData = () => {
  const { updateLastPrice, setConnectionStatus } = useTerminalStore();
  
  const handleMessage = useCallback((data) => {
    switch (data.type) {
      case 'trade':
        updateLastPrice(data.symbol, data.price);
        break;
      case 'quote':
        updateLastPrice(data.symbol, data.lastPrice);
        break;
      default:
        break;
    }
  }, [updateLastPrice]);

  const ws = useWebSocket('wss://stream.data.provider.com/v1/market', {
    onOpen: () => setConnectionStatus('marketData', true),
    onClose: () => setConnectionStatus('marketData', false),
    onMessage: handleMessage,
    reconnectInterval: 5000,
  });

  return ws;
};

/**
 * Hook for order book WebSocket connection
 */
export const useOrderBookData = (symbol) => {
  const { updateOrderBook, addTrade } = useOrderBookStore.getState?.() || {};
  
  const handleMessage = useCallback((data) => {
    switch (data.type) {
      case 'l2update':
        updateOrderBook?.(data.symbol, {
          bids: data.bids,
          asks: data.asks,
          sequence: data.sequence,
        });
        break;
      case 'trade':
        addTrade?.(data.symbol, {
          price: data.price,
          size: data.size,
          side: data.side,
          time: new Date().toISOString(),
          exchange: data.exchange,
        });
        break;
      default:
        break;
    }
  }, [updateOrderBook, addTrade]);

  const ws = useWebSocket(`wss://stream.data.provider.com/v1/orderbook/${symbol}`, {
    onMessage: handleMessage,
    reconnectInterval: 3000,
  });

  // Subscribe when connected
  useEffect(() => {
    if (ws.isConnected && symbol) {
      ws.subscribe('l2', [symbol]);
    }
  }, [ws.isConnected, symbol, ws.subscribe]);

  return ws;
};

/**
 * Hook for news WebSocket connection
 */
export const useNewsStream = () => {
  const { addArticle, setConnectionStatus } = useNewsStore.getState?.() || {};
  
  const handleMessage = useCallback((data) => {
    if (data.type === 'news') {
      addArticle?.(data.article);
    }
  }, [addArticle]);

  const ws = useWebSocket('wss://stream.data.provider.com/v1/news', {
    onOpen: () => setConnectionStatus?.('news', true),
    onClose: () => setConnectionStatus?.('news', false),
    onMessage: handleMessage,
  });

  return ws;
};
