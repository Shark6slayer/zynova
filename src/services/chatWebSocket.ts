import { apiClient, API_BASE_URL } from '../services/apiClient';

export type ChatSocketEventHandler = (data: any) => void;

class ChatWebSocketService {
  private socket: WebSocket | null = null;
  private listeners: Set<ChatSocketEventHandler> = new Set();
  private reconnectTimeout: any = null;
  private pingInterval: any = null;
  private isConnecting: boolean = false;

  public connect(): void {
    const token = apiClient.getToken();
    if (!token) return;
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isConnecting = true;
    try {
      // Convert http:// to ws:// or https:// to wss://
      const currentApiBase = apiClient.getApiBaseUrl();
      const wsBase = currentApiBase.startsWith('/')
        ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${currentApiBase}`
        : currentApiBase.replace(/^http(s)?:\/\//, 'ws$1://');
      const wsUrl = `${wsBase}/chat/ws?token=${encodeURIComponent(token)}`;

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.isConnecting = false;
        // Start keep-alive ping every 25 seconds
        if (this.pingInterval) clearInterval(this.pingInterval);
        this.pingInterval = setInterval(() => {
          if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send('ping');
          }
        }, 25000);
      };

      this.socket.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const parsed = JSON.parse(event.data);
          this.listeners.forEach((listener) => {
            try {
              listener(parsed);
            } catch (err) {
              console.error('Error in chat websocket listener:', err);
            }
          });
        } catch {
          // non-json frame
        }
      };

      this.socket.onclose = () => {
        this.isConnecting = false;
        this.cleanup();
        this.scheduleReconnect();
      };

      this.socket.onerror = () => {
        this.isConnecting = false;
        this.socket?.close();
      };
    } catch {
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    this.reconnectTimeout = setTimeout(() => {
      if (apiClient.getToken()) {
        this.connect();
      }
    }, 4000);
  }

  private cleanup(): void {
    if (this.pingInterval) clearInterval(this.pingInterval);
    this.pingInterval = null;
  }

  public disconnect(): void {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    this.cleanup();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  public subscribe(handler: ChatSocketEventHandler): () => void {
    this.listeners.add(handler);
    if (!this.socket || this.socket.readyState === WebSocket.CLOSED) {
      this.connect();
    }
    return () => {
      this.listeners.delete(handler);
    };
  }
}

export const chatWebSocketService = new ChatWebSocketService();
