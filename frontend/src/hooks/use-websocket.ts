"use client";

import { useEffect, useRef, useState } from "react";
import { isNativePlatform } from "@/lib/native";
import type { PluginListenerHandle } from "@capacitor/core";

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  reconnectInterval?: number;
  /** When false the socket will not connect. Defaults to true. */
  enabled?: boolean;
}

export function useWebSocket({
  url,
  onMessage,
  reconnectInterval = 3000,
  enabled = true,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const onMessageRef = useRef(onMessage);
  const enabledRef = useRef(enabled);

  // Keep refs in sync without triggering reconnects
  onMessageRef.current = onMessage;
  enabledRef.current = enabled;

  useEffect(() => {
    if (!enabled) return;

    let disposed = false;
    let appStateListener: PluginListenerHandle | null = null;

    function connect() {
      if (disposed) return;

      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessageRef.current(data);
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (!disposed && enabledRef.current) {
          reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    }

    connect();

    // Reconnect WebSocket when native app returns to foreground
    if (isNativePlatform()) {
      import("@capacitor/app").then(({ App }) => {
        App.addListener("appStateChange", ({ isActive }) => {
          if (isActive && enabledRef.current) {
            if (wsRef.current?.readyState !== WebSocket.OPEN) {
              connect();
            }
          }
        }).then((handle) => {
          appStateListener = handle;
        });
      });
    }

    return () => {
      disposed = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
      appStateListener?.remove();
    };
  }, [url, reconnectInterval, enabled]);

  return { isConnected };
}
