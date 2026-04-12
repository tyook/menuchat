import { useCallback, useEffect, useRef, useState } from "react";
import { fetchOrderQueue, type OrderQueueInfo } from "@/lib/api";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:5005";
const RECONNECT_INTERVAL = 3000;
const POLL_INTERVAL = 30000;

interface UseOrderQueueOptions {
  slug: string;
  orderId: string | null;
  enabled?: boolean;
}

export function useOrderQueue({ slug, orderId, enabled = true }: UseOrderQueueOptions) {
  const [queueInfo, setQueueInfo] = useState<OrderQueueInfo | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<NodeJS.Timeout>();
  const pollRef = useRef<NodeJS.Timeout>();
  const slugRef = useRef(slug);
  const orderIdRef = useRef(orderId);
  const enabledRef = useRef(enabled);
  const queueInfoRef = useRef(queueInfo);

  slugRef.current = slug;
  orderIdRef.current = orderId;
  enabledRef.current = enabled;
  queueInfoRef.current = queueInfo;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = undefined;
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    const oid = orderIdRef.current;
    const s = slugRef.current;
    if (!oid || !enabledRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const data = await fetchOrderQueue(s, oid);
        setQueueInfo(data);
      } catch {
        // Silently fail — will retry on next interval
      }
    }, POLL_INTERVAL);
  }, [stopPolling]);

  const connect = useCallback(() => {
    const oid = orderIdRef.current;
    const s = slugRef.current;
    if (!oid || !enabledRef.current) return;

    const qi = queueInfoRef.current;
    if (qi?.status === "ready" || qi?.status === "completed") return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    console.log("[WS] connecting to", `${WS_URL}/ws/order/${s}/${oid}/`);
    const ws = new WebSocket(`${WS_URL}/ws/order/${s}/${oid}/`);

    ws.onopen = () => {
      console.log("[WS] connected");
      setIsConnected(true);
      stopPolling();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("[WS] message", data);
        setQueueInfo(data);
        queueInfoRef.current = data;
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = (event) => {
      console.log("[WS] closed", { code: event.code, reason: event.reason, enabled: enabledRef.current });
      setIsConnected(false);
      // Only reconnect if still enabled and not intentionally closed
      if (enabledRef.current) {
        const currentQi = queueInfoRef.current;
        if (currentQi?.status === "ready" || currentQi?.status === "completed") return;
        startPolling();
        reconnectRef.current = setTimeout(connect, RECONNECT_INTERVAL);
      }
    };

    ws.onerror = (event) => { console.log("[WS] error", event); ws.close(); };
    wsRef.current = ws;
  }, [stopPolling, startPolling]);

  // Stop everything when order reaches terminal state
  useEffect(() => {
    const isTerminal = queueInfo?.status === "ready" || queueInfo?.status === "completed";
    if (isTerminal) {
      stopPolling();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    }
  }, [queueInfo?.status, stopPolling]);

  // Connect/disconnect effect — only re-runs when enabled or orderId changes
  useEffect(() => {
    if (!enabled || !orderId) return;
    enabledRef.current = true;
    connect();

    return () => {
      enabledRef.current = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      stopPolling();
      wsRef.current?.close();
    };
  }, [enabled, orderId, connect, stopPolling]);

  return {
    queuePosition: queueInfo?.queue_position ?? null,
    estimatedWait: queueInfo?.estimated_wait_minutes ?? null,
    status: queueInfo?.status ?? null,
    busyness: queueInfo?.busyness ?? null,
    isConnected,
  };
}
