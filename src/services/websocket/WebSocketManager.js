const connections = {};

export function createWSConnection(id, url, { onMessage, onOpen, onClose, onError, reconnect = true } = {}) {
  if (connections[id]?.ws?.readyState === WebSocket.OPEN) return connections[id];

  let retryCount = 0;
  const maxRetries = 10;

  function connect() {
    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        retryCount = 0;
        connections[id] = { ws, status: 'connected', url };
        onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage?.(data);
        } catch {
          onMessage?.(event.data);
        }
      };

      ws.onclose = () => {
        const wasIntentional = connections[id]?.intentionalClose;
        connections[id] = { ...connections[id], status: 'disconnected' };
        onClose?.();
        if (reconnect && !wasIntentional && retryCount < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
          retryCount++;
          setTimeout(connect, delay);
        }
      };

      ws.onerror = (err) => {
        connections[id] = { ...connections[id], status: 'error' };
        onError?.(err);
      };

      connections[id] = { ws, status: 'connecting', url };
    } catch (err) {
      console.warn(`[WS ${id}] Connection error:`, err.message);
    }
  }

  connect();
  return connections[id];
}

export function sendWSMessage(id, message) {
  const conn = connections[id];
  if (conn?.ws?.readyState === WebSocket.OPEN) {
    conn.ws.send(typeof message === 'string' ? message : JSON.stringify(message));
    return true;
  }
  return false;
}

export function closeWSConnection(id) {
  const conn = connections[id];
  if (conn?.ws) {
    // Mark as intentionally closed to suppress reconnection
    conn.intentionalClose = true;
    conn.ws.close();
    delete connections[id];
  }
}

export function getWSStatus(id) {
  return connections[id]?.status || 'disconnected';
}

export function getAllWSStatus() {
  const result = {};
  for (const [id, conn] of Object.entries(connections)) {
    result[id] = conn.status;
  }
  return result;
}
