import type { WSCallbacks, WSStatus } from '../../types/api';

interface WSConnectionEntry {
  ws: WebSocket;
  status: WSStatus;
  url: string;
  intentionalClose?: boolean;
}

interface CreateWSOptions extends WSCallbacks {
  reconnect?: boolean;
}

const connections: Record<string, WSConnectionEntry> = {};

export function createWSConnection(id: string, url: string, { onMessage, onOpen, onClose, onError, reconnect = true }: CreateWSOptions = { onMessage: () => {} }): WSConnectionEntry {
  if (connections[id]?.ws?.readyState === WebSocket.OPEN) return connections[id];

  let retryCount = 0;
  const maxRetries = 10;

  function connect(): void {
    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        retryCount = 0;
        connections[id] = { ws, status: 'connected', url };
        onOpen?.();
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data: unknown = JSON.parse(event.data as string);
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

      ws.onerror = (err: Event) => {
        connections[id] = { ...connections[id], status: 'error' };
        onError?.(err);
      };

      connections[id] = { ws, status: 'connecting', url };
    } catch (err) {
      console.warn(`[WS ${id}] Connection error:`, (err as Error).message);
    }
  }

  connect();
  return connections[id];
}

export function sendWSMessage(id: string, message: string | Record<string, unknown>): boolean {
  const conn = connections[id];
  if (conn?.ws?.readyState === WebSocket.OPEN) {
    conn.ws.send(typeof message === 'string' ? message : JSON.stringify(message));
    return true;
  }
  return false;
}

export function closeWSConnection(id: string): void {
  const conn = connections[id];
  if (conn?.ws) {
    // Mark as intentionally closed to suppress reconnection
    conn.intentionalClose = true;
    conn.ws.close();
    delete connections[id];
  }
}

export function getWSStatus(id: string): WSStatus {
  return connections[id]?.status || 'disconnected';
}

export function getAllWSStatus(): Record<string, WSStatus> {
  const result: Record<string, WSStatus> = {};
  for (const [id, conn] of Object.entries(connections)) {
    result[id] = conn.status;
  }
  return result;
}
